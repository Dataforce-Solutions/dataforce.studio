---
sidebar_position: 3
title: Prompt Optimization
---


# Prompt Optimization

Design, test, and improve prompts using AI assistance or your own data in an intuitive no-code interface.  
Whether you're exploring new prompt styles or refining existing ones with real-world data, our prompt optimization tools help you iterate quickly and effectively.  
Choose between AI-assisted suggestions to guide your creativity, or upload datasets to evaluate prompts at scale. No coding required — just drag, drop, and optimize.

#### Overview  
Prompt Optimization (Pre-release) is available under **Express Tasks**. It lets you construct and optimize LLM prompt flows using an intuitive, no-code builder — without writing a single line of code.

Choose between **AI-assisted** and **data-driven** optimization modes to iterate on prompt designs and maximize performance.

#### Prompt Optimization Options  
- **Free-form Optimization**: Get AI-powered prompt suggestions while keeping control over your writing style and intent.  
- **Data-Driven Optimization**: Upload your own dataset to optimize prompts based on actual performance metrics.

> Tip: To quickly explore the tool, click **"Use sample"** in the interface to auto-fill input/output examples.

#### Constructing & Optimizing LLM Flows  
- Build prompt pipelines by adding **Input**, **Prompt**, and **Output** nodes.  
- Define data types (`string`, `integer`, `float`) and field names.  
- Use **Set as a list** to test multiple examples at once.  
- Visually connect steps to define prompt logic and evaluation flow.  

#### Setting Up Model Providers  
1. Go to **Provider**.  
2. Connect your OpenAI or Ollama API key.  
3. Select the provider in the **Model Provider** dropdown.

#### Optimization Configurations  
- Set parameters such as **temperature**, **max tokens**, and **stop sequences**.  
- Create and compare multiple **prompt versions**.  
- Configure evaluation criteria (e.g., accuracy, helpfulness, relevance).

#### Running Optimizations  
1. Define input examples or upload a dataset.  
2. Choose prompt versions to test.  
3. Click **Run the model** to evaluate outputs.  
4. Compare outputs and metrics side-by-side.  
5. Use **Download model** to export your configuration.

#### Uploading Data (for Data-Driven Mode)  
- **Accepted format**: `.csv`  
- **Minimum rows**: 100  
- **Minimum columns**: 3  
- **Max file size**: 50 MB  

Required columns typically include:  
- `input`  
- `expected_output`  
- Any additional context field (optional)




