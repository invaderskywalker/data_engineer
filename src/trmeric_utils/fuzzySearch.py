from rapidfuzz import process, fuzz
import re

def squeeze_text(content: str) -> str:
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Remove leading/trailing whitespace
    content = content.strip()

    # Remove excessive blank lines (keep at most one)
    content = re.sub(r'\n\s*\n+', '\n', content)

    # For each line:
    lines = []
    for line in content.split('\n'):
        # Strip outer spaces but keep inner ones (for tables)
        line = line.strip()

        # If it's not a table-like line, collapse multiple spaces
        if not re.search(r'[|]| {2,}', line):  # avoid collapsing spaces in tables
            line = re.sub(r'\s{2,}', ' ', line)
        lines.append(line)

    # Join lines with a single newline
    content = '\n'.join(line for line in lines if line)

    # Final squeeze: remove stray spaces before punctuation
    content = re.sub(r'\s+([.,;:!?])', r'\1', content)

    return content

# def extract_phrases(text, min_length=2):
#     # Extract phrases of length >= min_length from the text
#     phrases = []
#     words = text.split()
#     for i in range(len(words)):
#         for j in range(i + min_length, len(words) + 1):
#             phrase = ' '.join(words[i:j])
#             phrases.append(phrase)
#     return phrases

def extract_phrases(text, min_length=2, max_length=5):
    # Extract phrases of length between min_length and max_length from the text
    phrases = []
    words = text.split()
    for n in range(min_length, min(max_length + 1, len(words) + 1)):
        for i in range(len(words) - n + 1):
            phrase = ' '.join(words[i:i + n])
            phrases.append(phrase)
    return phrases

def normalize_text(text):
    # Normalize text by lowercasing and stripping extra spaces
    return ' '.join(text.lower().strip().split())

def find_best_fuzzy_match(actual_names, big_text):
    normalized_actual_names = [normalize_text(name) for name in actual_names]
    partial_names = extract_phrases(big_text)
    normalized_partial_names = [normalize_text(phrase) for phrase in partial_names]
    
    print("debug -- partial_names -- find_best_fuzzy_match--", partial_names)

    best_match = {
        'partial_name': None,
        'actual_name': None,
        'score': 0
    }

    for partial_name in normalized_partial_names:
        # Find the best match for each normalized partial phrase
        match = process.extractOne(partial_name, normalized_actual_names, scorer=fuzz.token_set_ratio)
        print("----*********---", match[0], 
              "--", partial_names[normalized_partial_names.index(partial_name)],
              "--",actual_names[normalized_actual_names.index(match[0])], "--" , match[1])
        if match and match[1] > best_match['score'] and match[1] > 70:
            
            best_match = {
                'partial_name': partial_names[normalized_partial_names.index(partial_name)],
                'actual_name': actual_names[normalized_actual_names.index(match[0])],
                'score': match[1]
            }

    return best_match

import spacy
nlp = spacy.load("en_core_web_lg")
def detect_entities(text):
    doc = nlp(text)
    
    print("---**--", doc.ents)
    for token in doc:
        print("---**--", token, token.pos_)
        
    for ent in doc.ents:
        print("---**$$$--", ent.label_, ent.text)


# def find_closest_name(partial_name, name_list):
#     # Find the best match for the partial_name in the name_list
#     match, score = process.extractOne(partial_name, name_list)
#     return match, score

# def find_closest_name(partial_name, name_list):
#     # Find the best match for the partial_name in the name_list
#     match_info = process.extractOne(partial_name, name_list)
#     if match_info:
#         match, score, _ = match_info  # Extract the match and score (ignore the index)
#         return match, score
#     return None, 0


# def extract_potential_project_names(text):
#     # Process the text with SpaCy
#     doc = nlp(text)
    
#     # Extract potential names based on entity recognition and noun phrases
#     potential_names = set()
#     for ent in doc.ents:
#         # Add named entities (e.g., organizations) to potential names
#         if ent.label_ in ["ORG"]:  # You might want to use "ORG" for potential names
#             potential_names.add(ent.text)
    
#     # Add noun phrases to potential names
#     for chunk in doc.noun_chunks:
#         potential_names.add(chunk.text)
    
#     return potential_names

# def process_text_for_project_names(text, name_list):
#     print("process_text_for_project_names----", text)
#     # Extract potential project names from the text
#     potential_names = extract_potential_project_names(text)
#     print("process_text_for_project_names----", potential_names)
    
#     matches = []
#     for name in potential_names:
#         closest_name, score = find_closest_name(name, name_list)
#         if score > 80:  # Threshold for a good match
#             matches.append((name, closest_name, score))
    
#     print("debug hard process_text_for_project_names ---", matches)
#     return matches


# def fuzzy_match_and_replace_with_actual(text, actual_names) :
#     print("in fuzzy_match_and_replace_with_actual ", text)
#     # best_match = find_best_fuzzy_match(actual_names=list(actual_names), big_text=text)
#     # print("best match ", best_match)
#     # ntext = text
#     # if (best_match['score'] > 80 and best_match['partial_name'] and best_match['actual_name']):
#     #     ntext = re.sub(best_match['partial_name'],best_match['actual_name'], ntext )
        
#     # detect_entities(text)
#     process_text_for_project_names(text, actual_names)
    
#     return text

# # # Example usage
# # actual_names = ['Jane Doe', 'John Smith', 'Jani Doe', 'Jack Brown', 'Abhishek Kumar Singh']
# # big_text = 'Abihshek Kr S was mentioned in the meeting notes as one of the key contributors.'

# # match = find_best_match(actual_names, big_text)
# # print(f"Partial Name: {match['partial_name']}, Actual Name: {match['actual_name']}, Score: {match['score']}")




# def process_text_for_project_names(text, name_list):
#     print("process_text_for_project_names----", text)
#     # Extract potential project names from the text
#     potential_names = extract_potential_project_names(text)
#     print("process_text_for_project_names----", potential_names)
    
#     matches = []
#     for name in potential_names:
#         closest_name, score = find_closest_name(name, name_list)
#         if score > 80:  # Threshold for a good match
#             matches.append((name, closest_name, score))
    
#     print("debug hard process_text_for_project_names ---", matches)
#     return matches


def extract_potential_project_names(text):
    # Process the text with SpaCy
    doc = nlp(text)
    
    # Extract potential names based on entity recognition and noun phrases
    potential_names = set()
    
    # Define a list of stop words or common words to exclude
    stop_words = set(nlp.Defaults.stop_words)

    for ent in doc.ents:
        # Add named entities (e.g., organizations) to potential names
        if ent.label_ in ["ORG", "PRODUCT"]:  # Include other types if needed
            if len(ent.text.split()) > 1 and "project" not in ent.text.lower():  # Avoid single-word entities and exclude "project"
                potential_names.add(ent.text)
    
    # Add noun phrases to potential names, filtering out common or short phrases
    for chunk in doc.noun_chunks:
        # Filter out common stop words, very short phrases, and phrases containing "project"
        if len(chunk.text.split()) > 1 and chunk.text.lower() not in stop_words and "project" not in chunk.text.lower():
            potential_names.add(chunk.text)
            
    for token in doc:
        if token.pos_ == "PROPN" and token.text.lower() not in stop_words and "project" not in token.text.lower():
            potential_names.add(token.text)
    
    
    return potential_names

def find_closest_name(partial_name, name_list):
    # Find the best match for the partial_name in the name_list
    match_info = process.extractOne(partial_name, name_list)
    if match_info:
        match, score, _ = match_info  # Extract the match and score (ignore the index)
        return match, score
    return None, 0



def process_text_for_project_names(text, name_list):
    # Extract potential project names from the text
    potential_names = extract_potential_project_names(text)
    # print("process_text_for_project_names----", potential_names)
    
    if not potential_names:
        print("No potential names extracted.")
        return []

    # Store all matches with their scores
    all_matches = []

    for name in potential_names:
        # Find all potential matches for each name
        matches = process.extract(name, name_list, scorer=fuzz.token_sort_ratio, limit=10)
        # print(f"Matches for '{name}': {matches}")  # Debugging line

        for match in matches:
            closest_name, score, _ = match  # Unpack the match tuple correctly
            if score > 50:  # Threshold for a good match
                all_matches.append((name, closest_name, score))

    # Remove duplicate entries and sort by score
    unique_matches = list(set(all_matches))
    unique_matches.sort(key=lambda x: x[2], reverse=True)

    print("debug hard process_text_for_project_names ---", unique_matches)
    # return unique_matches
    
    # Second matching: Word matching
    word_matches = []
    for original_name, closest_name, score in unique_matches:
        # Split both the original name and closest name into words
        original_words = set(original_name.split())
        closest_words = set(closest_name.split())
        
        # Check for any common words between the two sets
        common_words = original_words.intersection(closest_words)
        if common_words:
            word_matches.append((original_name, closest_name, score, common_words))
    
    print("debug word_matches ---", word_matches)
    return word_matches



# def fuzzy_match_and_replace_with_actual(text, actual_names):
#     print("in fuzzy_match_and_replace_with_actual ", text, actual_names)
#     # Use process_text_for_project_names to find and replace
#     matches = process_text_for_project_names(text, list(actual_names))
    
#     # # Replace matches in the text
#     # for original_name, closest_name, _ in matches:
#     #     text = re.sub(re.escape(original_name), closest_name, text, flags=re.IGNORECASE)
    
    
#     # Replace matches in the text
#     for original_name, closest_name, score, common_words in matches:
#         text = re.sub(re.escape(original_name), closest_name, text, flags=re.IGNORECASE)
    
    
#     print("debug fuzzy_match_and_replace_with_actual ", text)
#     return text


def fuzzy_match_and_replace_with_actual(text, actual_names):
    # print("in fuzzy_match_and_replace_with_actual ", text, actual_names)
    
    # Use process_text_for_project_names to find and replace
    matches = process_text_for_project_names(text, list(actual_names))
    
    # Sort matches by score in descending order
    matches.sort(key=lambda x: -x[2])

    # Create a string from the sorted matches
    replacements = {}
    
    for original_name, closest_name, score, common_words in matches:
        # If original_name already has a replacement list, append to it; otherwise, create one
        if original_name in replacements:
            replacements[original_name].append(closest_name)
        else:
            replacements[original_name] = [closest_name]

    for original_name, closest_names in replacements.items():
        # Convert list to a string like "a, b, and c"
        if len(closest_names) > 1:
            formatted_replacement = ", ".join(closest_names[:-1]) + ", and " + closest_names[-1]
        else:
            formatted_replacement = closest_names[0]
        
        # Replace in the text
        text = re.sub(re.escape(original_name), formatted_replacement, text, flags=re.IGNORECASE)

    print("debug fuzzy_match_and_replace_with_actual ", text)
    return text
