from analyzer.ai_analyzer import analyze_with_ai

sample_content = """
Our company has raised $20 million in funding.
We are hiring Python developers.
We are launching a new AI product.
"""

result = analyze_with_ai(sample_content)

print("\nAI ANALYSIS")
print("-----------")
print(result)