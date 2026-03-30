kapruka-gift-concierge/
│
├── .env                          # API keys (never commit this!)
├── .gitignore                    # ignore .env, __pycache__, etc.
├── requirements.txt              # all dependencies
├── README.md                     # project documentation
│
├── data/                         # all data files
│   ├── catalog.json              # scraped product data
│   └── recipient_profiles.json  # semantic memory
│
├── part1_crawler/                
│   ├── scraper.py                # main playwright scraper
│   └── ingest.py                 # loads catalog.json → Qdrant
│
├── part2_memory/                 
│   ├── short_term.py             # conversation buffer
│   ├── long_term.py              # Qdrant vector store manager
│   └── semantic.py               # recipient profiles manager
│
├── part3_orchestration/          
│   ├── router.py                 # intent classifier
│   ├── catalog_agent.py          # RAG product search agent
│   └── logistics_agent.py        # delivery feasibility agent
│
├── part4_reflection/             
│   └── reflection_loop.py        # draft → reflect → revise
│
├── part5_performance/            
│   ├── metrics.py                # crawl success, latency etc.
│   └── report/                   
│       └── proposal.pdf          # 10-15 page technical report
│
├── bonus_ui/                     
│   └── app.py                    # Streamlit/Gradio frontend
│
├── notebooks/                    
│   ├── 01_crawler_demo.ipynb     # Part 1 walkthrough
│   ├── 02_memory_demo.ipynb      # Part 2 walkthrough
│   ├── 03_orchestration_demo.ipynb # Part 3 walkthrough
│   └── 04_reflection_demo.ipynb  # Part 4 walkthrough
│
└── main.py                       # entry point, ties everything