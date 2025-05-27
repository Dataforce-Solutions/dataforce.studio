---
sidebar_position: 3
title: Prompt Optimization
---

# Prompt Optimization

Define and automatically optimize LLM-based workflow — without writing code.
Prompt Optimization lets you design flexible LLM workflows using a visual builder.

Each logic path generates its own prompt, which the model follows step by step. With built-in flow control (via Gate and Processor nodes) and optional dataset evaluation, you can refine prompts until they consistently produce high-quality outputs.

Available under the **Express Tasks** tab, Prompt Optimization lets you build and test LLM prompt flows without writing a single line of code.

---

## Overview

Prompt Optimization supports two main workflows:

- **Free-form Optimization** – Optimize prompts without labelled datasets — just define the task logic and flow, and the system will generate prompts accordingly.  
- **Data-Driven Optimization** – Iteratively optimize prompts using both pipeline structure and labelled input-output data to improve task-specific performance.

To get started, open **Express Tasks** and select **Prompt Optimization**.

---

## Step-by-Step Guide

### 1. Select an Optimization Option

After entering Prompt Optimization, choose between:

- **Free-form Optimization** – Manually configure inputs/outputs and craft the logic.  
- **Data-Driven Optimization** automatically iterates and improves prompts using both pipeline structure and labelled dataset examples.

Once selected, a visual workflow builder editor will appear with two default blocks: **Input** and **Output**.

---
## Free-form Optimization
### 2. Configure Input and Output Fields

Click on the **Input** or **Output** nodes to set:

- **Data Type** – `string`, `integer`, or `float`.  
- **Field Name** – Define a label for each field (e.g., `user_query`, `answer`).  
- Add more fields with **"Add input/output field"** if needed.

---

### 3. Add Logic Nodes: Gate and Processor

Click the **+** icon (bottom-right toolbar) to add:

- **Gate**  
  - Provide a **Hint** – a guide used by the optimizer to generate the final gate logic.  
      _Example: Determine if the input data is in English or not._
  - Define **Input data type and name**.  
  - Add **Conditions** to define under which input criteria this node is triggered.    
      _Example: Condition — "English text" (input is in English), "Not English text" (input is not in English)._

- **Processor**
  - Provide a **Hint** – Give a brief description of how the input should be processed.
  - Set **Input and Output** fields similar to Gate.
  It takes input from upstream nodes and transforms it according to the provided processor hint.

Connect nodes visually to define the workflow. Processors can be chained and combined Gate nodes for advanced flows.  
Each node prepares its part of the final flow.
 

---

### 4. Set Up Model Provider

Before running prompts, configure the model backend:

1. Go to the **Provider** tab.  
2. Select the provider in the **Model Provider** dropdown (OpenAI supported, Ollama currently not available).
3. Add your API key.  
4. *(Optional)* Allow storing the API key in your browser’s local storage for future sessions.


---

### 5. Define Task Optimization Settings

Scroll to the **Task Optimization** section:

- **Task Description** – A summary of what the workflow should achieve.  
- The **Teacher Model** prepares the optimization logic and generates the "ideal prompts" based on hints and (optionally) a provided dataset.
- When ready, the **Student Model** is evaluated by running through the same workflow — using the optimized prompts to generate outputs.
After the Student model completes its run, the results can optionally be reviewed again by the Teacher model or evaluated using scoring metrics.
When the model is ready the model will be run by the Student model.

- **Evaluation Metrics**:  
  - `Exact Match` – Optimization continues until model output matches expected result exactly.   
  - `LLM-Based Scoring` – Measures similarity with a provided criteria to target output (ideal when exact match is too strict).   
  - `None` – Skip evaluation metrics.

---

### 6. Run Prompt Evaluation

1. Click **Run the Model** (top-right corner).  
2. Add input examples manually or upload a `.csv` file for batch testing.  
3. Click **Predict** to generate model outputs.  

---

##  Data-Driven Optimization
### 7. Upload Dataset for Data-Driven Optimization

If using a dataset:

#### File Requirements:

- **File Size**: Up to 50 MB  
- **Columns**: At least 2  
- **Rows**: Minimum 10 rows

You can either:

- Upload your own `.csv` file  
- Or use the **Sample Dataset**, which includes two example columns:  
  - `phrase`  
  - `translated formal phrase`

Once the dataset is loaded, you can configure column behaviour using the **Set type for each column** tool.

#### Column Configuration Features:

- Use **Find column** to search by name  
- Define columns as `input` or `output`  
- Sort columns alphabetically (A–Z) or in reverse (Z–A)  
- Use **Edit Columns** to rename or modify columns  
- Use **Export** to download the modified dataset  

Once you finish configuration, click **Continue** to move to the workflow editor where you can define the workflow logic and see your optimized prompt flow in action.

---

## Quick Tips
  
- You can chain multiple gates and processors for advanced workflows.
- Use smaller models (e.g., gpt-4o) for testing before scaling up to larger models to save costs.
- Store your API key in local storage to avoid re-entering it each session.

---





