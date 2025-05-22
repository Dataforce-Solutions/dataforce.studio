---
sidebar_position: 3
title: Prompt Optimization
---

---
sidebar_position: 3
title: Prompt Optimization
---

# Prompt Optimization

Design, test, and improve prompts using AI assistance or your own data — all within an intuitive no-code interface.  
Whether you're exploring new prompt styles or refining existing ones with real-world data, Prompt Optimization helps you iterate quickly and effectively.

Available under the **Express Tasks** tab, Prompt Optimization (Pre-release) lets you build and test LLM prompt flows without writing a single line of code.

---

## Overview

Prompt Optimization supports two main workflows:

- **Free-form Optimization** – Create and tweak prompts using AI-generated suggestions.  
- **Data-Driven Optimization** – Upload datasets and evaluate prompt performance at scale.

To get started, open **Express Tasks** and select **Prompt Optimization (Pre-release)**.

---

## Step-by-Step Guide

### 1. Select an Optimization Option

After entering Prompt Optimization, choose between:

- **Free-form Optimization** – Manually configure inputs/outputs and craft prompt logic.  
- *(Data-Driven Optimization option is coming soon or available conditionally.)*

Once selected, a visual prompt flow editor will appear (similar to a Miro board) with two default blocks: **Input** and **Output**.

---

### 2. Configure Input and Output Fields

Click on the **Input** or **Output** nodes to set:

- **Data Type** – `string`, `integer`, or `float`.  
- **Field Name** – Define a label for each field (e.g., `user_query`, `answer`).  
- **Set as a List** – Enable this option to test with multiple examples.  
- Add more fields with **"Add input/output field"** if needed.

---

### 3. Add Logic Nodes: Gate or Processor

Click the **+** icon (bottom-right toolbar) to add:

- **Gate**  
  - Add a **Hint** – This is the actual prompt instruction shown to the model.  
  - Define **Input data type and name**.  
  - Optionally add **Conditions** to trigger logic (e.g., `if language = EN`).

- **Processor**  
  - Add a **Hint** – Typically, a transformation or instruction prompt.  
  - Set **Input and Output** fields similar to Gate.

Connect nodes visually to define the prompt flow.

---

### 4. Set Up Model Provider

Before running prompts, configure the model backend:

1. Go to the **Provider** tab.  
2. Add your API key (OpenAI supported, Ollama currently not available).  
3. Select the provider in the **Model Provider** dropdown.

---

### 5. Define Task Optimization Settings

Scroll to the **Task Optimization** section:

- **Task Description** – A summary of what the prompt should achieve.  
- **Teacher Model** – Reference model used for ideal output.  
- **Student Model** – The model being tested/optimized.  
  > Tip: Use smaller models for quicker testing.

- **Evaluation Metrics**:  
  - `Exact Match` – Output must match expected text (currently not available).  
  - `LLM-Based Scoring` – Evaluate based on similarity or scoring (currently not available).  
  - `None` – Skip evaluation metrics.

---

### 6. Run Prompt Evaluation

1. Click **Run the Model** (top-right corner).  
2. Add input examples manually or upload a `.csv` file for batch testing.  
3. Click **Predict** to generate model outputs.  
4. Review and compare outputs and scores.

---

### 7. (Optional) Upload Dataset for Data-Driven Optimization

If using a dataset:

- **Accepted format**: `.csv`  
- **Requirements**:
  - Minimum 100 rows  
  - At least 3 columns: `input`, `expected_output`, plus optional `context`  
  - Max file size: 50 MB  

Click **Upload File**, then **Predict** to evaluate performance on the dataset.

---

## Quick Tips
  
- You can chain multiple gates and processors for advanced workflows.  
- Smaller models = faster iteration.

---





