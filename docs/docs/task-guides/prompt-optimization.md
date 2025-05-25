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
- **Data-Driven Optimization** enables you to iteratively improve prompts using both pipeline structure and labelled dataset examples.

Once selected, a visual prompt flow editor will appear (similar to a Miro board) with two default blocks: **Input** and **Output**.

---
## Free-form Optimization
### 2. Configure Input and Output Fields

Click on the **Input** or **Output** nodes to set:

- **Data Type** – `string`, `integer`, or `float`.  
- **Field Name** – Define a label for each field (e.g., `user_query`, `answer`).  
- **Set as a List** – Enable this option to test with multiple examples.  
- Add more fields with **"Add input/output field"** if needed.

---

### 3. Add Logic Nodes: Gate and Processor

Click the **+** icon (bottom-right toolbar) to add:

- **Gate**  
  - Provide a **Hint** – a guide used by the optimizer to generate the final prompt logic.
  - Define **Input data type and name**.  
  - Add **Conditions** to define under which input criteria this node is triggered.


- **Processor**
- Provide a **Hint** – This serves as a transformation instruction.
- Set **Input and Output** fields similar to Gate.
Each Processor uses its Hint to build a specific prompt that is sent to the model.  
It takes input from upstream nodes and transforms it according to the defined logic.

Connect nodes visually to define the prompt flow. Just like Gate nodes, Processors can be chained and combined with Conditions for advanced flows.  
Each node prepares its part of the final prompt, and the model proceeds through the entire flow using those prompts.
 

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

- **Task Description** – A summary of what the prompt should achieve.  
- The **Teacher Model** prepares the optimization logic and generates the "ideal prompts" based on hints and (optionally) a provided dataset.
- When ready, the **Student Model** is evaluated by running through the same workflow — using the optimized prompts to generate outputs.
After the Student model completes its run, the results can optionally be reviewed again by the Teacher model or evaluated using scoring metrics.
 You can then run the Student model multiple times to improve its match to the Teacher’s output.
  > Tip: Use smaller models for quicker testing.

- **Evaluation Metrics**:  
  - `Exact Match` – Optimization continues until model output matches expected result exactly.   
  - `LLM-Based Scoring` – Measures similarity to target output (ideal when exact match is too strict).   
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
  > *(Note: Browser must allow downloads to enable this)*

Once you finish configuration, click **Continue** to move to the workflow editor where you can define the logic and see your optimized prompt flow in action.

---


---

## Quick Tips
  
- You can chain multiple gates and processors for advanced workflows.
- You can use **Conditions** to guide model behaviour based on inputs.
- Smaller models = faster iteration.
- Store your API key in local storage to avoid re-entering it each session.


---





