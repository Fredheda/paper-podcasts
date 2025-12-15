# ArXiv API Search Guide

This guide explains how to use advanced search options with the `ArxivService` methods.

## Table of Contents
- [Basic Search](#basic-search)
- [Search Prefixes](#search-prefixes)
- [Boolean Operators](#boolean-operators)
- [Wildcards](#wildcards)
- [Category Codes](#category-codes)
- [Complex Query Examples](#complex-query-examples)
- [Best Practices](#best-practices)

---

## Basic Search

The simplest search is just keywords:

```python
# Search for papers containing these keywords anywhere
papers = service.search_by_topic("machine learning")
papers = service.search_by_topic("neural networks")
papers = service.search_by_topic("quantum computing")
```

---

## Search Prefixes

Use prefixes to search specific fields:

| Prefix | Field | Example |
|--------|-------|---------|
| `ti:` | Title | `ti:transformer` |
| `au:` | Author | `au:Hinton` |
| `abs:` | Abstract | `abs:convolutional` |
| `cat:` | Category | `cat:cs.AI` |
| `all:` | All fields | `all:deep learning` |

### Title Search (`ti:`)

```python
# Search for "transformer" in title
papers = service.search_by_topic("ti:transformer")

# Exact phrase in title (use quotes)
papers = service.search_by_topic('ti:"attention is all you need"')

# Multiple words (all must appear)
papers = service.search_by_topic("ti:neural AND ti:networks")
```

**Or use the dedicated method:**
```python
# Fuzzy title search
papers = service.search_by_title("attention is all you need", exact=False)

# Exact title search
papers = service.search_by_title("Attention Is All You Need", exact=True)
```

### Author Search (`au:`)

```python
# Search by author last name
papers = service.search_by_topic("au:Vaswani")

# Search by full name
papers = service.search_by_topic("au:Geoffrey Hinton")

# Multiple authors
papers = service.search_by_topic("au:Hinton AND au:LeCun")
```

### Abstract Search (`abs:`)

```python
# Search in abstract
papers = service.search_by_topic("abs:reinforcement learning")

# Combine with other fields
papers = service.search_by_topic("ti:transformer AND abs:attention")
```

### Category Search (`cat:`)

```python
# Search in specific category
papers = service.search_by_topic("cat:cs.AI")

# Multiple categories
papers = service.search_by_topic("cat:cs.AI OR cat:cs.LG")

# Category + keywords
papers = service.search_by_topic("cat:cs.AI AND quantum")
```

---

## Boolean Operators

Combine search terms with boolean operators:

| Operator | Description | Example |
|----------|-------------|---------|
| `AND` | Both terms must appear | `quantum AND computing` |
| `OR` | Either term can appear | `neural OR network` |
| `ANDNOT` | First term must appear, second must not | `machine ANDNOT learning` |

### AND Operator

```python
# Both "machine" and "learning" must appear
papers = service.search_by_topic("machine AND learning")

# Multiple AND conditions
papers = service.search_by_topic("ti:transformer AND au:Vaswani AND cat:cs.CL")

# Across different fields
papers = service.search_by_topic("ti:attention AND abs:mechanism")
```

### OR Operator

```python
# Either term can appear
papers = service.search_by_topic("transformer OR attention")

# Multiple options
papers = service.search_by_topic("cat:cs.AI OR cat:cs.LG OR cat:cs.CV")

# Author alternatives
papers = service.search_by_topic("au:Hinton OR au:LeCun OR au:Bengio")
```

### ANDNOT Operator

```python
# Machine learning papers, but not deep learning
papers = service.search_by_topic("machine learning ANDNOT deep")

# AI papers excluding computer vision
papers = service.search_by_topic("cat:cs.AI ANDNOT cat:cs.CV")

# Papers with neural networks but not convolutional
papers = service.search_by_topic("ti:neural ANDNOT ti:convolutional")
```

---

## Wildcards

Use wildcards for flexible matching:

| Wildcard | Description | Example |
|----------|-------------|---------|
| `*` | Match zero or more characters | `optim*` matches "optimize", "optimization", "optimal" |
| `?` | Match exactly one character | `ne?ral` matches "neural", "neoral" |

### Examples

```python
# Match "neural", "neuronal", "neuro", etc.
papers = service.search_by_topic("ti:neur*")

# Match "optimization", "optimisation", "optimizer", etc.
papers = service.search_by_topic("abs:optim*")

# Match different spellings
papers = service.search_by_topic("abs:optimi?ation")
```

---

## Category Codes

Common arXiv categories for computer science and related fields:

### Computer Science

| Code | Description |
|------|-------------|
| `cs.AI` | Artificial Intelligence |
| `cs.CL` | Computation and Language (NLP) |
| `cs.CV` | Computer Vision and Pattern Recognition |
| `cs.LG` | Machine Learning |
| `cs.NE` | Neural and Evolutionary Computing |
| `cs.RO` | Robotics |
| `cs.CR` | Cryptography and Security |
| `cs.DB` | Databases |
| `cs.DS` | Data Structures and Algorithms |
| `cs.HC` | Human-Computer Interaction |

### Mathematics

| Code | Description |
|------|-------------|
| `math.ST` | Statistics Theory |
| `math.OC` | Optimization and Control |
| `math.PR` | Probability |
| `math.NA` | Numerical Analysis |

### Physics

| Code | Description |
|------|-------------|
| `physics.comp-ph` | Computational Physics |
| `quant-ph` | Quantum Physics |

### Statistics

| Code | Description |
|------|-------------|
| `stat.ML` | Machine Learning (Statistics) |
| `stat.AP` | Applications |
| `stat.TH` | Theory |

**Full list:** https://arxiv.org/category_taxonomy

---

## Complex Query Examples

### Example 1: Recent Transformer Papers by Specific Authors

```python
papers = service.search_by_topic(
    topic="ti:transformer AND (au:Vaswani OR au:Dosovitskiy)",
    max_results=10,
    sort_by_recent=True
)
```

### Example 2: Machine Learning Papers Excluding Deep Learning

```python
papers = service.search_by_topic(
    topic="cat:cs.LG ANDNOT (deep OR neural)",
    max_results=20,
    sort_by_recent=False  # Sort by relevance
)
```

### Example 3: Computer Vision Papers with "attention" in Title

```python
papers = service.search_by_topic(
    topic="cat:cs.CV AND ti:attention",
    max_results=15
)
```

### Example 4: NLP Papers by Multiple Authors

```python
papers = service.search_by_topic(
    topic="cat:cs.CL AND (au:Bengio OR au:Hinton OR au:LeCun)",
    max_results=10
)
```

### Example 5: Papers on "GAN" or "Generative Adversarial Networks"

```python
papers = service.search_by_topic(
    topic='ti:GAN OR ti:"generative adversarial"',
    max_results=20
)
```

### Example 6: Recent AI Papers with "explainability" or "interpretability"

```python
papers = service.search_by_topic(
    topic="cat:cs.AI AND (explainability OR interpretability)",
    max_results=10,
    sort_by_recent=True
)
```

### Example 7: Optimization Papers Excluding Specific Keywords

```python
papers = service.search_by_topic(
    topic="ti:optim* ANDNOT (quantum OR genetic)",
    max_results=15
)
```

### Example 8: Cross-Domain Search

```python
# Papers at intersection of machine learning and quantum physics
papers = service.search_by_topic(
    topic="(cat:cs.LG OR cat:stat.ML) AND cat:quant-ph",
    max_results=10
)
```

### Example 9: Papers with Specific Keywords in Abstract

```python
papers = service.search_by_topic(
    topic='abs:"self-supervised learning" AND cat:cs.CV',
    max_results=10
)
```

### Example 10: Broad Topic with Multiple Constraints

```python
papers = service.search_by_topic(
    topic="(ti:reinforcement AND ti:learning) AND cat:cs.AI AND abs:robot*",
    max_results=20,
    sort_by_recent=True
)
```

---

## Best Practices

### 1. Use Quotes for Exact Phrases

```python
# Good: Exact phrase
papers = service.search_by_topic('ti:"attention is all you need"')

# Less precise: Individual words
papers = service.search_by_topic("ti:attention is all you need")
```

### 2. Combine Categories for Broader Coverage

```python
# Machine learning appears in multiple categories
papers = service.search_by_topic(
    topic="(cat:cs.LG OR cat:stat.ML) AND transformer"
)
```

### 3. Use Wildcards for Terminology Variations

```python
# Catches "optimization", "optimisation", "optimizer", etc.
papers = service.search_by_topic("ti:optim*")
```

### 4. Parentheses for Complex Queries

```python
# Clear precedence
papers = service.search_by_topic(
    topic="(ti:neural OR ti:deep) AND (cat:cs.CV OR cat:cs.AI)"
)
```

### 5. Sort by Relevance for Keyword Searches

```python
# For keyword searches, relevance is often better
papers = service.search_by_topic(
    topic="transformer attention mechanism",
    sort_by_recent=False  # Sort by relevance
)

# For staying current, use recent
papers = service.search_by_topic(
    topic="cat:cs.AI",
    sort_by_recent=True  # Sort by date
)
```

### 6. Start Broad, Then Narrow

```python
# Start with a broad search
papers = service.search_by_topic("reinforcement learning", max_results=100)

# If too many results, add constraints
papers = service.search_by_topic(
    topic="reinforcement learning AND cat:cs.AI ANDNOT game",
    max_results=20
)
```

### 7. Test Queries with Small max_results First

```python
# Test your query first
papers = service.search_by_topic(
    topic="complex AND query AND here",
    max_results=5  # Small number for testing
)

# Once satisfied, increase
papers = service.search_by_topic(
    topic="complex AND query AND here",
    max_results=50
)
```

---

## Common Pitfalls

### ❌ Don't Forget Quotes for Multi-Word Phrases

```python
# Wrong: Will search for "machine" OR "learning" separately
papers = service.search_by_topic("ti:machine learning")

# Right: Searches for exact phrase
papers = service.search_by_topic('ti:"machine learning"')
```

### ❌ Boolean Operators Must Be Uppercase

```python
# Wrong: Lowercase won't work
papers = service.search_by_topic("neural and network")

# Right: Uppercase
papers = service.search_by_topic("neural AND network")
```

### ❌ Watch Out for Special Characters

```python
# Some special characters may need escaping or quotes
papers = service.search_by_topic('ti:"C++ programming"')
```

---

## Quick Reference Cheat Sheet

```python
# Simple keyword
service.search_by_topic("neural networks")

# Title only
service.search_by_topic("ti:transformer")

# Exact title phrase
service.search_by_topic('ti:"attention is all you need"')

# Author
service.search_by_topic("au:Hinton")

# Category
service.search_by_topic("cat:cs.AI")

# Multiple categories
service.search_by_topic("cat:cs.AI OR cat:cs.LG")

# AND operator
service.search_by_topic("machine AND learning")

# OR operator
service.search_by_topic("transformer OR attention")

# ANDNOT operator
service.search_by_topic("neural ANDNOT convolutional")

# Wildcard
service.search_by_topic("optim*")

# Complex query
service.search_by_topic(
    topic="(ti:neural OR ti:deep) AND cat:cs.CV AND au:Hinton",
    max_results=10,
    sort_by_recent=True
)
```

---

## Additional Resources

- **arXiv API User Manual**: https://arxiv.org/help/api/user-manual
- **arXiv Category Taxonomy**: https://arxiv.org/category_taxonomy
- **arXiv Subject Classifications**: https://arxiv.org/help/arxiv_identifier
