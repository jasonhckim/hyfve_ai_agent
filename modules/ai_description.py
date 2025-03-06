import openai
import json
import re
import yaml

# ✅ Load OpenAI prompt from YAML
with open("openai_prompts.yaml", "r") as f:
    prompts = yaml.safe_load(f)

generate_description_prompt = prompts["generate_description_prompt"]

def generate_description(style_number, images, keywords):
    """Generates product descriptions using OpenAI and tracks used keywords."""
    is_set = "SET" in style_number.upper()
    set_text = "This style is a coordinated clothing set." if is_set else ""

    keyword_list = ", ".join(keywords[:50])  # Use up to 50 keywords

    # ✅ Format the prompt with dynamic values
    formatted_prompt = generate_description_prompt.format(
        style_number=style_number,
        keywords=keyword_list,
        set_text=set_text
    )

    response = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": "You are a fashion expert."},
                  {"role": "user", "content": [{"type": "text", "text": formatted_prompt}] + images}]
    )

    raw_text = response.choices[0].message.content

    try:
        parsed_data = json.loads(raw_text)
        description = parsed_data.get("description", "")

        # ✅ Identify which keywords were actually used
        used_keywords = [kw for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', description, re.IGNORECASE)]
        used_keywords_str = ", ".join(used_keywords) if used_keywords else "None"

        return {
            "Style Number": style_number,
            "Product Title": parsed_data.get("product_title", "N/A"),
            "Product Description": description,
            "Tags": ", ".join(parsed_data.get("hashtags", [])),
            "Product Category": parsed_data.get("product_category", "N/A"),
            "Product Type": "Set" if is_set else parsed_data.get("product_type", "N/A"),
            "Option2 Value": parsed_data.get("key_attribute", "N/A"),
            "Keywords": used_keywords_str  # ✅ Track the keywords used in the description
        }
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Failed to parse JSON for {style_number}. Debug: {e}")
        return None
