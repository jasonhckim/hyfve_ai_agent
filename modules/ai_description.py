import openai
import json
import re
import yaml
import time

# ✅ Load OpenAI prompt from YAML
with open("openai_prompts.yaml", "r") as f:
    prompts = yaml.safe_load(f)

generate_description_prompt = prompts["generate_description_prompt"]

def generate_description(style_number, images, keywords, max_retries=3):
    """Generates product descriptions using OpenAI and tracks used keywords."""
    is_set = "SET" in style_number.upper()
    set_text = "This style is a coordinated clothing set." if is_set else ""

    keyword_list = ", ".join(keywords[:3])  # Use up to 3 keywords

    # ✅ Strengthen the instruction for keyword usage
    formatted_prompt = generate_description_prompt.format(
        style_number=style_number,
        keywords=keyword_list,
        set_text=set_text
    ) + f"\n\nEnsure that the following keywords are seamlessly included in the description: {keyword_list}. If necessary, rephrase the description naturally to integrate these keywords."


    for attempt in range(max_retries):
        try:
            print(f"\n🔍 DEBUG: Sending request to OpenAI for {style_number}...")

            response = openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "system", "content": "You are a fashion expert."},
                          {"role": "user", "content": [{"type": "text", "text": formatted_prompt}] + images}]
            )

            # ✅ Print OpenAI response
            raw_text = response.choices[0].message.content.strip()
            print(f"\n🔍 DEBUG: OpenAI Response for {style_number}: {response}")

            # ✅ Remove Markdown-style code blocks (```json ... ```)
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()  # Remove ```json at start and ``` at end
                
            parsed_data = json.loads(raw_text)

            # ✅ Clean fields to prevent formatting issues
            description = parsed_data.get("description", "").replace("\n", " ").strip()
            product_title = parsed_data.get("product_title", "").replace("\n", " ").strip()
            product_category = parsed_data.get("product_category", "N/A").strip()
            product_type = "Set" if is_set else parsed_data.get("product_type", "N/A").strip()
            key_attribute = parsed_data.get("key_attribute", "N/A").strip()

            # ✅ Identify which keywords were actually used
            used_keywords = [kw for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', description, re.IGNORECASE)]
            used_keywords_str = ", ".join(used_keywords) if used_keywords else ""

            return {
                "Style Number": style_number,
                "Product Title": product_title,
                "Product Description": description,
                "Tags": ", ".join(parsed_data.get("hashtags", [])),
                "Product Category": product_category,
                "Product Type": product_type,
                "Option2 Value": key_attribute,
                "Keywords": used_keywords_str
            }
        
        except openai.OpenAIError as api_error:
            print(f"❌ OpenAI API Error for {style_number}: {api_error}")
            time.sleep(2)  # ✅ Small delay before retrying
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ ERROR: Failed to parse JSON for {style_number}. Attempt {attempt + 1} of {max_retries}. Debug: {e}")
            time.sleep(2)  # ✅ Small delay before retrying

    # ✅ Return a fallback response after all retries fail
    print(f"❌ ERROR: All {max_retries} attempts failed for {style_number}. Skipping.")
    return {
        "Style Number": style_number,
        "Product Title": "N/A",
        "Product Description": "Failed to generate description.",
        "Tags": "N/A",
        "Product Category": "N/A",
        "Product Type": "N/A",
        "Option2 Value": "N/A",
        "Keywords": "N/A"
    }
