# Property Match Recommender System (Explainable Recommendation Engine)

An end-to-end, explainable **property–user matching system** built as part of a data science assignment.  
The project designs a **custom Match Score**, ranks properties for each user, and presents the results through a **clean, interactive Streamlit web interface**.

This repository contains:

- The **recommendation UI**
- Documentation of the **match-score logic**
- Instructions to **run locally on macOS and Windows**
- A **portfolio-ready demo** suitable for interviews

---

## Problem Statement

Given:

- A dataset describing **user preferences** (budget, location, property type, size, etc.)
- A dataset describing **property attributes** (price, size, bedrooms, condition, year built, etc.)

The goal is to:

1. Design a **quantitative matching function**
2. Compute a **Match Score** for each user–property pair
3. Rank properties for each user
4. Present results in a **clear, interpretable, and explainable UI**

---

## What This Project Achieves

✔ Converts subjective preferences into a **numerical match score**  
✔ Balances **hard constraints** (e.g., budget) with **soft preferences**  
✔ Produces **transparent, explainable recommendations**  
✔ Demonstrates **end-to-end system thinking** (data → logic → UI)

---

## Overall Approach (High-Level)

### Step 1: Data Understanding

- User preferences and property attributes are treated as **structured features**
- All features are normalized or mapped into comparable scales

### Step 2: Feature Engineering

For each user–property pair, we compute:

- Budget fit
- Location alignment
- Size alignment
- Bedroom/Bathroom match
- Property condition match

Each component is normalized to `[0, 1]`.

### Step 3: Match Score Design

A **weighted linear combination** is used to compute the final score:
