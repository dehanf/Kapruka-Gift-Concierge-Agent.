""""

takes user query -> embed it -> 
    retrieve from the store -> 
        then check filters -> 
            drop similar products with filters(cosine similarity) -> 
                if nothing then fetch again with k*2


                
                filters = {
                exclude
                }

"""

import numpy as np
from sentence_transformers import SentenceTransformer
from infrastructure.db.qdrant_store import get_client, COLLECTION_NAME
from qdrant_client.models import Distance, VectorParams
from config import LT_EMBEDDING_MODEL, LT_SEARCH_TOP_K

def cosine_similarity(vec1 : list , vec2 : list):
    a = np.array(vec1)
    b = np.array(vec2)

    return float(np.dot(a,b) / (np.linalg.norm(a) * np.linalg.norm(b)) )



def search_catalog(query : str, top_k : int = LT_SEARCH_TOP_K):

    encoder = SentenceTransformer(LT_EMBEDDING_MODEL)
    query_vector = encoder.encode(query).tolist()

    client = get_client()

    results = client.query_points(
        collection_name = COLLECTION_NAME,
        query = query_vector,
        limit =top_k
    ).points

    products = [hit.payload for hit in results]
    return products


def main():
    print("=== Long Term Memory Test ===\n")

    query = "birthday cake for my wife"
    print(f"Query: {query}")
    print("-" * 40)

    results = search_catalog(query, top_k=5)

    for i, product in enumerate(results, 1):
        print(f"\n{i}. {product.get('name')}")
        print(f"   Price       : {product.get('price')}")
        print(f"   Category    : {product.get('category')}")
        print(f"   Availability: {product.get('availability')}")

if __name__ == "__main__":
    main()