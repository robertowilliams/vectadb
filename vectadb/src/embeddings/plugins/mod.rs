// Embedding provider plugins
pub mod cohere;
pub mod huggingface;
pub mod openai;
pub mod voyage;

pub use cohere::CoherePlugin;
pub use huggingface::HuggingFacePlugin;
pub use openai::OpenAIPlugin;
pub use voyage::VoyagePlugin;
