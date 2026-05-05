"""
Fetch the AI/ML-history Wikipedia corpus.

Writes one .txt per article to data/raw_articles/. Skips articles already
on disk so re-runs are cheap. Reports running token count via tiktoken
(GPT-4 tokenizer — close enough to Gemini's tokenizer for sizing the
2M-token corpus required by the hackathon).

Usage:
    python scripts/fetch_dataset.py
    python scripts/fetch_dataset.py --limit 20      # quick smoke test
    python scripts/fetch_dataset.py --list-only     # print titles + exit
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import wikipediaapi
import tiktoken


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "raw_articles"

USER_AGENT = "DevRAG-Hackathon/0.1 (https://github.com/Nilanshjain/DevRAG; benchmark-research)"


# Curated AI/ML history corpus. Picked for high cross-linking — the same
# entities (researchers, labs, methods) recur across many of these pages,
# which is exactly the structure GraphRAG should exploit better than
# vector RAG.
ARTICLES: dict[str, list[str]] = {
    "researchers": [
        "Geoffrey Hinton", "Yann LeCun", "Yoshua Bengio", "Andrew Ng",
        "Demis Hassabis", "Ilya Sutskever", "Andrej Karpathy", "Ian Goodfellow",
        "Fei-Fei Li", "Jürgen Schmidhuber", "Stuart J. Russell", "Peter Norvig",
        "Michael I. Jordan", "Ruslan Salakhutdinov", "Kaiming He",
        "Christopher Manning", "Tomas Mikolov", "Jeff Dean", "Kyunghyun Cho",
        "Alex Krizhevsky", "Sepp Hochreiter", "John McCarthy",
        "Marvin Minsky", "Frank Rosenblatt", "Judea Pearl", "Richard S. Sutton",
        "David Silver (computer scientist)", "Oriol Vinyals", "Pieter Abbeel",
        "Sergey Levine", "Chelsea Finn", "Dario Amodei", "Sam Altman",
        "Jan Leike", "Paul Christiano (AI researcher)",
    ],
    "labs_orgs": [
        "OpenAI", "DeepMind", "Google Brain", "Meta AI", "Anthropic",
        "Microsoft Research", "IBM Research", "Allen Institute for AI",
        "Mila (research institute)", "Stanford Artificial Intelligence Laboratory",
        "MIT Computer Science and Artificial Intelligence Laboratory",
        "Berkeley Artificial Intelligence Research", "Hugging Face",
        "Cohere", "Mistral AI", "xAI (company)", "Tesla, Inc.",
        "Machine Intelligence Research Institute", "Center for AI Safety",
    ],
    "methods_architectures": [
        "Transformer (deep learning architecture)", "Attention (machine learning)",
        "BERT (language model)", "Generative pre-trained transformer",
        "Reinforcement learning from human feedback", "Mixture of experts",
        "Diffusion model", "Recurrent neural network", "Long short-term memory",
        "Gated recurrent unit", "Convolutional neural network", "Residual neural network",
        "Generative adversarial network", "Variational autoencoder",
        "Reinforcement learning", "Q-learning", "Deep reinforcement learning",
        "Backpropagation", "Dropout (neural networks)", "Batch normalization",
        "Word2vec", "GloVe", "Self-supervised learning", "Contrastive learning",
        "Few-shot learning", "Zero-shot learning", "Transfer learning",
        "Fine-tuning (deep learning)", "Prompt engineering", "Chain-of-thought prompting",
        "Retrieval-augmented generation", "Knowledge graph",
        "Graph neural network", "AlphaZero", "Monte Carlo tree search",
        "Policy gradient", "Proximal policy optimization", "Actor-critic algorithm",
        "Beam search", "Stochastic gradient descent", "Adam (optimization algorithm)",
    ],
    "datasets_benchmarks": [
        "ImageNet", "MNIST database", "CIFAR-10", "COCO (dataset)",
        "GLUE (benchmark)", "SuperGLUE", "SQuAD", "Massive Multitask Language Understanding",
        "HellaSwag", "Winograd schema challenge", "BIG-bench",
        "Common Crawl", "The Pile (dataset)",
    ],
    "products_models": [
        "GPT-2", "GPT-3", "GPT-4", "ChatGPT", "Claude (language model)",
        "Gemini (chatbot)", "Llama (language model)", "PaLM",
        "AlphaGo", "AlphaFold", "Stable Diffusion", "DALL-E",
        "Midjourney", "Sora (text-to-video model)", "Whisper (speech recognition system)",
        "GitHub Copilot", "Cursor (code editor)",
    ],
    "concepts": [
        "Artificial intelligence", "Machine learning", "Deep learning",
        "Neural network", "Natural language processing", "Computer vision",
        "Speech recognition", "Artificial general intelligence",
        "AI alignment", "AI safety", "Existential risk from artificial general intelligence",
        "History of artificial intelligence", "AI winter",
        "Symbolic artificial intelligence", "Connectionism",
        "Embedding (machine learning)", "Tokenization (lexical analysis)",
        "Foundation model", "Large language model", "Multimodal learning",
        "Vector database",
    ],
    "foundational_researchers": [
        "Alan Turing", "Claude Shannon", "John McCarthy (computer scientist)",
        "Marvin Minsky", "Frank Rosenblatt", "Walter Pitts", "Warren Sturgis McCulloch",
        "John Hopfield", "David Rumelhart", "Seymour Papert", "Donald O. Hebb",
        "Allen Newell", "Herbert A. Simon", "Arthur Samuel", "Edward Feigenbaum",
        "Raj Reddy", "Patrick Henry Winston", "Terry Winograd", "Roger Schank",
        "Doug Lenat", "Edsger W. Dijkstra",
    ],
    "modern_researchers_extended": [
        "Pedro Domingos", "Tom M. Mitchell", "Daphne Koller", "Sebastian Thrun",
        "Vladimir Vapnik", "Leo Breiman", "Trevor Hastie", "Robert Tibshirani",
        "Aaron Courville", "François Chollet", "Soumith Chintala", "Jeff Dean",
        "John Schulman", "Greg Brockman", "Mira Murati", "Wojciech Zaremba",
        "Jakob Uszkoreit", "Aidan Gomez", "Noam Shazeer", "Jared Kaplan",
        "Tom Brown (computer scientist)", "Dawn Song", "Percy Liang",
        "Christopher D. Manning", "Daniel Jurafsky", "Ronald J. Williams",
        "Hugo Larochelle", "Pascal Vincent", "Razvan Pascanu",
        "Karen Simonyan", "Alex Graves (computer scientist)",
        "Volodymyr Mnih", "David Silver (programmer)",
        "Eric Horvitz", "Cynthia Dwork", "Lex Fridman", "Margaret Mitchell (scientist)",
        "Timnit Gebru", "Emily M. Bender", "Aleksander Madry",
        "Sara Hooker", "Chris Olah",
    ],
    "architectures_extended": [
        "Perceptron", "Multilayer perceptron", "Autoencoder",
        "Restricted Boltzmann machine", "Deep belief network", "Hopfield network",
        "Boltzmann machine", "Self-organizing map", "Vision transformer",
        "U-Net", "ResNet", "AlexNet", "LeNet", "VGGNet", "Inception (deep learning)",
        "EfficientNet", "DenseNet", "MobileNet", "YOLO (algorithm)", "R-CNN",
        "Mask R-CNN", "Capsule neural network", "Liquid neural network",
        "Spiking neural network", "Mamba (deep learning architecture)",
    ],
    "methods_extended": [
        "Word embedding", "Word2vec", "GloVe (machine learning)", "FastText",
        "Sentence embedding", "ELMo", "BERT (language model)", "T5 (language model)",
        "Cross-validation (statistics)", "Regularization (mathematics)",
        "Hyperparameter optimization", "Neural architecture search",
        "Model compression", "Knowledge distillation", "LoRA (machine learning)",
        "Direct preference optimization", "Constitutional AI",
        "Curriculum learning", "Active learning (machine learning)",
        "Federated learning", "Differential privacy",
        "Adversarial machine learning", "Adversarial example",
        "Boosting (machine learning)", "Gradient boosting", "XGBoost",
        "Random forest", "Decision tree learning",
        "Support vector machine", "K-nearest neighbors algorithm",
        "Naive Bayes classifier", "Logistic regression",
        "Linear regression", "Principal component analysis",
        "Independent component analysis", "T-distributed stochastic neighbor embedding",
        "K-means clustering", "DBSCAN", "Hierarchical clustering",
        "Expectation-maximization algorithm", "Bayesian network",
        "Hidden Markov model", "Markov decision process",
        "Monte Carlo method", "Variational autoencoder",
        "Normalizing flow", "Score-based generative model",
        "Energy-based model", "Latent diffusion model", "ControlNet",
        "Mixture of Gaussians", "Mixture model", "Topic model",
        "Latent Dirichlet allocation", "Recommender system",
        "Collaborative filtering", "Matrix factorization",
        "Genetic algorithm", "Evolutionary algorithm",
        "Reinforcement learning from AI feedback",
        "Inverse reinforcement learning", "Imitation learning",
        "Soft actor-critic", "Deep Q-network",
    ],
    "frameworks_and_hardware": [
        "TensorFlow", "PyTorch", "Keras", "JAX (software)", "Theano (software)",
        "Scikit-learn", "Pandas (software)", "NumPy", "SciPy",
        "Hugging Face", "Apache Spark", "Ray (software)",
        "Graphics processing unit", "Tensor Processing Unit", "AI accelerator",
        "CUDA", "ROCm", "OpenCL", "Field-programmable gate array",
        "Nvidia", "Advanced Micro Devices", "Intel", "TSMC",
        "Cerebras", "Graphcore", "SambaNova Systems", "Groq",
    ],
    "products_extended": [
        "DeepSeek", "Qwen", "Mixtral", "Phi (language model)",
        "Grok (chatbot)", "Copilot (Microsoft)",
        "Cursor (code editor)", "Tabnine", "Replit",
        "Stable Diffusion", "Imagen (text-to-image model)", "Flux (text-to-image model)",
        "Suno AI", "Runway (company)",
        "AlphaCode", "OpenAI o1", "Devin AI",
        "AlphaStar (software)", "OpenAI Five", "Pluribus (poker bot)",
        "Libratus", "Watson (computer)", "Deep Blue (chess computer)",
        "Stockfish (chess)", "Leela Chess Zero",
    ],
    "datasets_extended": [
        "WikiText", "OpenWebText", "C4 (dataset)", "LAION",
        "Stanford Sentiment Treebank", "IMDB (dataset)",
        "Common Voice", "LibriSpeech", "TIMIT",
        "Penn Treebank", "WordNet", "ConceptNet",
        "Open Images", "ADE20K", "Cityscapes (dataset)",
        "Pascal VOC dataset",
    ],
    "ethics_safety_society": [
        "Algorithmic bias", "Fairness (machine learning)",
        "Explainable artificial intelligence", "Interpretability",
        "Mechanistic interpretability", "Reward hacking",
        "Specification gaming", "Goodhart's law", "Goal misgeneralization",
        "Mesa-optimization", "Instrumental convergence",
        "Intelligence explosion", "Technological singularity",
        "Friendly artificial intelligence", "AI takeover",
        "AI capability control", "Coordination problem (AI)",
        "Algorithmic accountability", "Regulation of artificial intelligence",
        "EU AI Act", "Open letter on artificial intelligence",
        "Pause Giant AI Experiments: An Open Letter",
        "Frontier Model Forum",
    ],
    "history_and_culture": [
        "Dartmouth workshop", "Turing test", "Chinese room",
        "ELIZA", "PARRY", "SHRDLU", "Cyc",
        "AlphaGo versus Lee Sedol", "AlphaGo versus Ke Jie",
        "IBM Watson", "Loebner Prize", "Eugene Goostman",
        "Tay (chatbot)", "Microsoft Tay",
        "Logic Theorist", "General Problem Solver",
        "Mycin", "Dendral",
        "Cybernetics", "Information theory", "Computational complexity theory",
    ],
    "concepts_extended": [
        "Artificial neural network", "Cognitive architecture",
        "Cognitive computing", "Expert system", "Logic programming",
        "Prolog", "Lisp (programming language)", "Computational neuroscience",
        "Bayesian inference", "Probabilistic programming",
        "Causal inference", "Causality", "Game theory",
        "Multi-agent system", "Swarm intelligence", "Genetic programming",
        "Simulated annealing", "Particle swarm optimization",
        "Artificial life", "Embodied cognition", "Computational learning theory",
        "Probably approximately correct learning",
        "VC dimension", "Bias-variance tradeoff",
        "Curse of dimensionality", "Manifold hypothesis",
        "Universal approximation theorem", "No free lunch theorem",
        "Information bottleneck method",
        "Long tail", "Power law", "Scaling laws",
        "Chinchilla (language model)", "Emergent abilities of large language models",
    ],
    "books": [
        "Superintelligence: Paths, Dangers, Strategies",
        "Life 3.0", "Human Compatible", "The Master Algorithm",
        "Algorithms to Live By: The Computer Science of Human Decisions",
        "Artificial Intelligence: A Modern Approach",
        "Pattern Recognition and Machine Learning",
        "The Book of Why", "Gödel, Escher, Bach",
        "Society of Mind", "On Intelligence",
        "I Am a Strange Loop", "Our Final Invention",
    ],
    "robotics_and_autonomy": [
        "Robotics", "Humanoid robot", "Industrial robot",
        "Self-driving car", "Autonomous vehicle", "Waymo",
        "Boston Dynamics", "Tesla Autopilot", "Tesla Bot",
        "Roomba", "iRobot",
    ],
    "conferences_and_awards": [
        "Turing Award", "Conference on Neural Information Processing Systems",
        "International Conference on Machine Learning",
        "Association for the Advancement of Artificial Intelligence",
    ],
    "ai_thinkers": [
        "Nick Bostrom", "Eliezer Yudkowsky", "Max Tegmark",
        "Hans Moravec", "Ray Kurzweil",
    ],
    "ml_tooling": [
        "Open Neural Network Exchange", "Caffe (software)",
        "Apache MXNet", "MLOps",
    ],
}


def slugify(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower()
    return s[:120]


def all_titles() -> list[tuple[str, str]]:
    """Returns (category, title) pairs."""
    return [(cat, t) for cat, titles in ARTICLES.items() for t in titles]


def fetch(wiki: wikipediaapi.Wikipedia, title: str) -> str | None:
    page = wiki.page(title)
    if not page.exists():
        return None
    # page.text is the full article body (sections concatenated, no markup).
    return page.text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Fetch only N articles (for testing)")
    parser.add_argument("--list-only", action="store_true", help="Print article titles and exit")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds between requests")
    args = parser.parse_args()

    titles = all_titles()
    if args.limit is not None:
        titles = titles[: args.limit]

    if args.list_only:
        for cat, t in titles:
            print(f"[{cat}] {t}")
        print(f"\nTotal: {len(titles)} articles across {len(ARTICLES)} categories")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wiki = wikipediaapi.Wikipedia(language="en", user_agent=USER_AGENT)
    enc = tiktoken.get_encoding("cl100k_base")

    total_tokens = 0
    fetched = 0
    skipped = 0
    missing: list[str] = []

    for i, (category, title) in enumerate(titles, 1):
        out_path = OUT_DIR / f"{slugify(title)}.txt"
        if out_path.exists():
            text = out_path.read_text(encoding="utf-8")
            total_tokens += len(enc.encode(text))
            skipped += 1
            print(f"[{i}/{len(titles)}] cached  {title}")
            continue

        text = fetch(wiki, title)
        if text is None:
            print(f"[{i}/{len(titles)}] MISSING {title}", file=sys.stderr)
            missing.append(title)
            continue

        # Prepend a small header so chunking can keep the source visible.
        header = f"Title: {title}\nCategory: {category}\nSource: Wikipedia\n\n"
        out_path.write_text(header + text, encoding="utf-8")
        tok = len(enc.encode(header + text))
        total_tokens += tok
        fetched += 1
        print(f"[{i}/{len(titles)}] fetched {title}  ({tok:,} tokens)")
        time.sleep(args.sleep)

    print()
    print(f"Fetched:        {fetched}")
    print(f"Already cached: {skipped}")
    print(f"Missing:        {len(missing)}")
    print(f"Total tokens:   {total_tokens:,}  (target: >=2,000,000)")
    print(f"Output dir:     {OUT_DIR}")

    if missing:
        print("\nMissing titles (consider replacements):")
        for t in missing:
            print(f"  - {t}")

    if total_tokens < 2_000_000:
        print(f"\nWARNING: below 2M token target by {2_000_000 - total_tokens:,} tokens.")
        print("Add more articles to ARTICLES in scripts/fetch_dataset.py.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
