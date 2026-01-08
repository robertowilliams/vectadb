import chromadb
from sentence_transformers import SentenceTransformer

# Initialize client
chroma_client = chromadb.Client()

# Create a test collection
collection = chroma_client.get_or_create_collection("test_vecs")

# Load embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Test data
docs = [
    "The Eiffel Tower is in Paris.",
    "The highest mountain is Everest.",
]

embeddings = embedder.encode(docs).tolist()

# Insert
collection.add(
    ids=["1", "2"],
    documents=docs,
    embeddings=embeddings
)

print("Inserted data.")

# Query
query = "Where is the Eiffel Tower?"
query_embedding = embedder.encode([query]).tolist()

results = collection.query(
    query_embeddings=query_embedding,
    n_results=2
)

print("Query results:", results)
