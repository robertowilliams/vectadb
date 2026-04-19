// FileTailer — tracks byte offsets per file and yields new lines each poll.
//
// Design decisions:
//   • Tracks the byte offset (not line number) so a seek + read always lands
//     at exactly the right byte, even for variable-width UTF-8 content.
//   • Detects file rotation / truncation by comparing the stored offset against
//     the current file size: if size < offset the file was replaced or cleared,
//     so we reset to zero and read from the top.
//   • On first access, respects `lookback_lines`: if > 0, seeks backward to
//     capture the last N lines of existing content; otherwise starts at EOF
//     so only future writes are tailed.
//   • Incomplete lines (no trailing '\n') are buffered and returned on the
//     next poll once the writer has flushed them.

use anyhow::{Context, Result};
use chrono::Utc;
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use tracing::{debug, warn};

use crate::models::LogLine;

/// State tracked per watched file.
#[derive(Debug)]
struct FileState {
    /// Byte offset of the next unread byte.
    offset: u64,
    /// Incomplete line buffered from the previous poll.
    partial: String,
    /// Whether we have performed the initial seek (first-poll lookback).
    initialized: bool,
}

/// Tails multiple log files, yielding new [`LogLine`]s on each [`poll`] call.
pub struct FileTailer {
    states: HashMap<PathBuf, FileState>,
    lookback_lines: usize,
}

impl FileTailer {
    pub fn new(lookback_lines: usize) -> Self {
        Self {
            states: HashMap::new(),
            lookback_lines,
        }
    }

    /// Read all lines appended to `path` since the last poll.
    ///
    /// Returns an empty Vec (not an error) when there is nothing new.
    pub fn poll(&mut self, path: &Path, agent_id: &str, session_id: Option<&str>) -> Result<Vec<LogLine>> {
        let canonical = path
            .canonicalize()
            .unwrap_or_else(|_| path.to_path_buf());

        // ── Open the file ────────────────────────────────────────────────────
        let mut file = match std::fs::File::open(path) {
            Ok(f) => f,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                debug!("Log file not found (will retry): {}", path.display());
                return Ok(vec![]);
            }
            Err(e) => {
                return Err(e).with_context(|| format!("Cannot open {}", path.display()));
            }
        };

        let file_size = file.metadata()?.len();
        let state = self.states.entry(canonical.clone()).or_insert(FileState {
            offset: 0,
            partial: String::new(),
            initialized: false,
        });

        // ── First-poll initialisation ────────────────────────────────────────
        if !state.initialized {
            state.initialized = true;
            if self.lookback_lines == 0 {
                // Start from current EOF — only tail future writes
                state.offset = file_size;
            } else {
                // Seek backward to capture the last `lookback_lines` lines
                state.offset = find_lookback_offset(&mut file, file_size, self.lookback_lines)?;
            }
        }

        // ── Rotation / truncation detection ─────────────────────────────────
        if file_size < state.offset {
            warn!(
                "File shrunk ({} < {}), resetting offset — rotation detected: {}",
                file_size, state.offset, path.display()
            );
            state.offset = 0;
            state.partial.clear();
        }

        // Nothing new
        if file_size == state.offset {
            return Ok(vec![]);
        }

        // ── Read new bytes ────────────────────────────────────────────────────
        file.seek(SeekFrom::Start(state.offset))?;
        let mut reader = BufReader::new(file);

        let mut lines: Vec<LogLine> = Vec::new();
        let mut current_offset = state.offset;

        loop {
            let mut raw_line = String::new();
            let bytes_read = reader
                .read_line(&mut raw_line)
                .with_context(|| format!("Error reading {}", path.display()))?;

            if bytes_read == 0 {
                break; // EOF
            }

            current_offset += bytes_read as u64;

            if raw_line.ends_with('\n') {
                // Complete line — prepend any buffered partial content
                let complete = if state.partial.is_empty() {
                    raw_line.trim_end_matches('\n').trim_end_matches('\r').to_string()
                } else {
                    let mut s = std::mem::take(&mut state.partial);
                    s.push_str(raw_line.trim_end_matches('\n').trim_end_matches('\r'));
                    s
                };

                if !complete.is_empty() {
                    lines.push(LogLine {
                        file_path: path.to_string_lossy().to_string(),
                        agent_id: agent_id.to_string(),
                        session_id: session_id.map(str::to_string),
                        byte_offset: state.offset,
                        raw: complete,
                        read_at: Utc::now(),
                    });
                }
            } else {
                // Incomplete line — buffer it for next poll
                state.partial.push_str(&raw_line);
            }
        }

        state.offset = current_offset;
        debug!(
            "Polled {} — read {} new line(s) (offset now {})",
            path.display(),
            lines.len(),
            state.offset
        );
        Ok(lines)
    }
}

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

/// Return the byte offset of the start of the line that is `n` lines from the
/// end of the file.  Falls back to 0 (start of file) if the file is shorter.
fn find_lookback_offset<F: Read + Seek>(file: &mut F, file_size: u64, n_lines: usize) -> Result<u64> {
    if file_size == 0 {
        return Ok(0);
    }

    // Read the whole file into memory only if it's small enough; otherwise
    // scan backwards in chunks to find the N-th newline from the end.
    const CHUNK: u64 = 65_536; // 64 KiB

    let mut lines_found: usize = 0;
    let mut scan_pos = file_size;

    while scan_pos > 0 {
        let chunk_start = scan_pos.saturating_sub(CHUNK);
        let chunk_len = (scan_pos - chunk_start) as usize;

        file.seek(SeekFrom::Start(chunk_start))?;
        let mut buf = vec![0u8; chunk_len];
        file.read_exact(&mut buf)?;

        // Count newlines scanning from the end of the chunk
        for (i, &b) in buf.iter().enumerate().rev() {
            if b == b'\n' {
                lines_found += 1;
                if lines_found > n_lines {
                    // The line after this newline is what we want
                    let offset = chunk_start + i as u64 + 1;
                    return Ok(offset);
                }
            }
        }

        scan_pos = chunk_start;
    }

    // Fewer than n_lines lines in the file — start from the beginning
    Ok(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    fn write_lines(content: &str) -> NamedTempFile {
        let mut f = NamedTempFile::new().unwrap();
        f.write_all(content.as_bytes()).unwrap();
        f.flush().unwrap();
        f
    }

    #[test]
    fn test_tail_new_lines() {
        let f = write_lines("line1\nline2\nline3\n");
        let mut tailer = FileTailer::new(0);
        // First poll with lookback=0 → starts at EOF, no lines
        let lines = tailer.poll(f.path(), "agent", None).unwrap();
        assert!(lines.is_empty(), "Expected no lines on first poll (tail mode)");
    }

    #[test]
    fn test_lookback_lines() {
        let f = write_lines("line1\nline2\nline3\nline4\nline5\n");
        let mut tailer = FileTailer::new(2);
        let lines = tailer.poll(f.path(), "agent", None).unwrap();
        assert_eq!(lines.len(), 2);
        assert_eq!(lines[0].raw, "line4");
        assert_eq!(lines[1].raw, "line5");
    }

    #[test]
    fn test_incremental_reads() {
        use std::io::Write;
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "first").unwrap();
        f.flush().unwrap();

        let mut tailer = FileTailer::new(100); // read all
        let lines1 = tailer.poll(f.path(), "agent", None).unwrap();
        assert_eq!(lines1.len(), 1);

        // Append more content
        writeln!(f, "second").unwrap();
        writeln!(f, "third").unwrap();
        f.flush().unwrap();

        let lines2 = tailer.poll(f.path(), "agent", None).unwrap();
        assert_eq!(lines2.len(), 2);
        assert_eq!(lines2[0].raw, "second");
        assert_eq!(lines2[1].raw, "third");
    }

    #[test]
    fn test_rotation_detection() {
        use std::io::Write;
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "before rotation").unwrap();
        f.flush().unwrap();

        let mut tailer = FileTailer::new(100);
        tailer.poll(f.path(), "agent", None).unwrap();

        // Simulate rotation: truncate file
        f.as_file_mut().set_len(0).unwrap();
        f.as_file_mut().seek(SeekFrom::Start(0)).unwrap();
        writeln!(f, "after rotation").unwrap();
        f.flush().unwrap();

        let lines = tailer.poll(f.path(), "agent", None).unwrap();
        assert_eq!(lines.len(), 1);
        assert_eq!(lines[0].raw, "after rotation");
    }
}
