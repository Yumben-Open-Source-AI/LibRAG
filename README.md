<div align="center">
<img src="./log(500x500).png" width="300px" alt="xorbits" />

<p align="center">
  <a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-454545?style=for-the-badge"></a>
  <a href="./README_zh_CN.md"><img alt="简体中文版自述文件" src="https://img.shields.io/badge/中文介绍-d9d9d9?style=for-the-badge"></a>
  <a href="./README_ja_JP.md"><img alt="日本語のREADME" src="https://img.shields.io/badge/日本語-d9d9d9?style=for-the-badge"></a>
</p>
</div>
<br />


# LibRAG  
LibRAG is a groundbreaking general-purpose intelligent content retrieval engine that redefines document preprocessing and passage retrieval through full-pipeline model inference capabilities. The product eliminates complex components such as embedding models and vector databases, leveraging the deep semantic understanding of large language models (LLMs) to achieve end-to-end precise retrieval and recall. It is suitable for various AI applications, including enterprise knowledge management, domain-specific Q&A, compliance review, medical case retrieval, financial risk control, and AI agents.  

# Architecture Overview  
The system employs multi-level semantic parsing + unified indexing technology to transform text into retrievable knowledge units, enabling on-demand precision recall and answer generation through a semantic routing layer.  

![image](https://github.com/user-attachments/assets/00f1562b-52bc-480e-b1f4-e08b589db54b)  

# Core Technological Breakthroughs  
## 1. Intelligent Document Preprocessing Engine  
Dynamic Structured Parsing: Supports automated parsing of multi-format documents (PDF, Word, TXT, MarkDown) using a hybrid segmentation algorithm (sliding window + semantic boundary detection) to generate coherent text chunks, addressing semantic fragmentation issues in traditional chunking methods.  

Content Quality Enhancement: Built-in LLM multi-agents enable preprocessing tasks such as error correction and sensitive information redaction, ensuring data integrity and compliance (e.g., automatic anonymization of patient information in medical documents).  

## 2. Inference-Driven Passage Retrieval Mechanism  
Semantic Reasoning Matching: Directly analyzes multi-dimensional relationships between user queries and document passages using model inference, replacing traditional vector similarity calculations. Capable of identifying implicit logical relationships (e.g., causal chains, comparative arguments).  

Hybrid Retrieval Strategy: Combines keyword matching with deep semantic reasoning scores, achieving precise content localization through a proprietary weighting algorithm. Retrieval accuracy is improved by over 40% compared to traditional methods.  

## 3. AI-Native Index Structure  
Innovative Indexing: Does not rely on embedding models, vector databases, or graph databases. Pioneers an AI-native efficient indexing structure tailored to the characteristics of LLM technology.  

## 4. Self-Evolving Maintenance-Free Architecture  
Self-Evolving: Modifications to the document library automatically trigger fine-tuning of the knowledge base index, with routine documents synchronized at the minute level to meet timeliness requirements in fields like finance and law.  

Maintenance-Free: Precision does not degrade as documents accumulate, eliminating reliance on manual optimization or intervention.  

# Key Advantages Over Traditional RAG  

| Dimension         | Traditional RAG Solutions                                | LibRAG Solution                                  |
|------------------|---------------------------------------------------------|-------------------------------------------------|
| Tech Stack Complexity | Requires integration of embedding models + vector DBs + reranking models | Single inference model-driven, streamlined architecture |
| Retrieval Accuracy | <50% without expert tuning; high tuning costs with uncertain results | >90% out-of-the-box, easily adjustable by non-experts |
| Maintenance Cost | Heavy manual intervention (labeling, chunking, vector matching algorithm iteration, embedding model fine-tuning) | Fully automated, self-evolving, maintenance-free |
| Domain Adaptability | Requires customization per vertical domain (embedding models, prompts, standard questions) | Universally applicable across domains |  

# Technical Challenges - Precision RAG  

## Multi-Hop Problems:  
The "multi-hop problem" refers to scenarios where information must be extracted from multiple data sources or steps to arrive at an answer. For example, determining a company's three-year compound growth rate may require analyzing multiple reports and comparing them with competitors' performance.  

## Routing Problems:  
Similar documents (e.g., financial reports from different years) often share close content, leading to potential loss of critical information (e.g., year indicators) during processing, which compromises accuracy.  

## Structured Data Processing:  
Enterprises possess vast amounts of structured data (e.g., databases, Excel files). Integrating such data with RAG without precision loss remains a challenge.  

## Technical Boundaries:  
RAG is only one component of an application. Ensuring seamless collaboration with other technologies (e.g., function calls) without over-reliance on RAG is crucial.
