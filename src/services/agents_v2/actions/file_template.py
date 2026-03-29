import re
import json
import traceback
from typing import Dict
from datetime import datetime
from src.database.dao import db_instance
from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.api.logging.AppLogger import appLogger
from src.utils.fuzzySearch import squeeze_text

MODEL_OPTS =  ModelOptions(model="gpt-4.1",max_tokens=15000,temperature=0.1)

def create_template_mapping(
    file_content: str,
    original_filename: str,
    s3_key: str,
    category: str,
    template_name: str,
    user_id: int,
    tenant_id: int,
    session_id: str,
    llm=None
) -> Dict:
    """
    Converts raw extracted document text into a clean, professional Markdown template.
    Shows user for approval before saving.
    """
    raw_text = squeeze_text(file_content)
    if not raw_text:
        return {
            "success": False,
            "message": "The uploaded file appears to be empty.",
            "needs_clarification": True,
            "clarification_question": "Please upload a valid document with content."
        }

    template_name = template_name or original_filename.split('.')[0]

    try:
        system_prompt = f"""
            You are Trucible, a world-class document formatting expert.

            Your task: Convert the raw extracted text from a business document (Project Charter, BRD, Proposal, etc.) 
            into a clean, professional, and beautifully structured Markdown format.

            RULES:
            - Use proper Markdown syntax:
            - # for main title
            - ## for section headers
            - **Bold** for field labels (e.g., **Project Name:**, **Business Need:**)
            - Tables with | --- | alignment where appropriate
            - Bullet lists (- ) or numbered lists (1.) based on content
            - Preserve logical flow and hierarchy
            - Make it visually scannable and executive-ready
            - Use consistent spacing: one blank line between sections
            - Do NOT add any commentary, notes, or explanations
            - Do NOT invent content — only reformat what's there
            - If there are key-value pairs (e.g., "Project Manager: Jennie Shin"), format as:
            **Project Manager:** Jennie Shin

            INPUT DOCUMENT TYPE: {category}
            ORIGINAL FILENAME: {original_filename}

            RAW EXTRACTED TEXT:
            {raw_text}

            OUTPUT ONLY clean Markdown. Start directly with the title.
            **Output format**
            ```markdown 

            ```
        """

        user_prompt = "Convert this document into a clean, professional Markdown template."

        chat = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)
        
        response = llm.run(chat,MODEL_OPTS,function_name="create_template_mapping",
            logInDb={"tenant_id": tenant_id, "user_id": user_id}
        ).strip()

        print("\n\n--- RAW LLM RESPONSE ---\n", response, "\n--- END ---\n")

        # Extract markdown block
        if "```markdown" in response.lower():
            md = response.split("```markdown", 1)[1]
            md = md.split("```", 1)[0].strip()
        elif "```" in response:
            parts = response.split("```")
            md = parts[1] if len(parts) > 1 else parts[0]
            md = md.strip()
            if md.lower().startswith("markdown"):
                md = md[8:].strip()
        else:
            md = response.strip()

        # Final cleanup
        md = md.strip()
        if not md.startswith("#"):
            md = f"# {template_name}\n\n" + md

        preview = md[:2400]
        if len(md) > 2400:
            preview += "\n\n---\n*Preview truncated. Full template will be saved upon confirmation.*"

        return {
            "success": True,
            "mode": "template_extracted",
            "category": category,
            "template_name": template_name,
            "original_filename": original_filename,
            "original_s3_key": s3_key,
            "generated_document": md,           # Full clean Markdown
            "preview": preview,                 # For display
            "message": f"I've converted your uploaded document into a clean Markdown template for **{category}**.\n\nHere’s how it looks:",
            "needs_confirmation": True,
            "clarification_question": 
                "Does this formatting look good to you?\n"
                "• Tables aligned?\n"
                "• Headings and labels clear?\n"
                "• Lists and sections correct?\n\n"
                "Reply **'Yes, save it'** to make this your official template.\n"
                "Or tell me what to adjust (e.g., 'Make Scope a table', 'Use bullets instead of numbers')."
        }

    except Exception as e:
        appLogger.error({
            "function": "create_template_mapping",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "tenant_id": tenant_id
        })
        return {
            "success": False,
            "message": "Failed to convert document to Markdown template.",
            "needs_clarification": True,
            "clarification_question": "Please try uploading the file again. Supported: DOCX, PDF."
        }








# def create_template_mapping(
#     file_content: str,
#     original_filename: str,
#     s3_key: str,
#     mode: str,
#     template_name: str,
#     category: str,
#     changes: str,
#     user_id: int,
#     tenant_id: int,
#     session_id: str,
#     user_satisfied: bool = False,
#     llm = None,
#     limit = 5
# ) -> Dict:
#     """
#     Takes raw extracted text from a document (DOCX/PDF) and returns a clean,
#     beautifully formatted Markdown template for user review.
    
#     Output: Preview of structured Markdown with headings, bold labels,
#             tables, lists, paragraphs — ready for confirmation.
#     """
#     raw_text = squeeze_text(file_content)
#     # raw_text = file_content
#     # markdown_structure = convert_raw_doc_text_to_markdown(file_content)
#     print("--desbug structs marksdown-------", raw_text,"\n\n")
#     if mode == "save_template":
#         user_satisfied = True
#         template_record = {
#             "template_id": str(uuid.uuid4()),
#             "template_name": template_name,
#             "category": category,
#             "original_filename": original_filename,
#             "original_s3_key": s3_key,
#             "structure_markdown": raw_text,
#             "saved_at": datetime.now().isoformat(),
#             "is_active": True,
#         }

#         return {
#             "success": True,
#             "mode": mode,
#             "template_record": template_record,
#             "preview": raw_text[:1800] + ("\n\n... (truncated)" if len(raw_text) > 1800 else ""),
#             "message": f"Template '{template_name}' saved!\nI'll use this exact format for future {category}s.",
#             "user_satisfied": user_satisfied,
#         }

#     else:
#         if not changes.strip():
#             return {
#                 "success": False,
#                 "mode": mode,
#                 "needs_clarification": True,
#                 "clarification_question": "What changes would you like?",
#                 "message": "I'm ready to generate your document using your template. Please share the changes!",
#                 "user_satisfied": False,
#             }
        
#         try:

#             # Extract first 5-10 lines to anchor the output style
#             lines = raw_text.splitlines()
#             first_few_lines = "\n".join(lines[:limit])  # Adjust based on typical header size
#             if len(lines) > limit:
#                 first_few_lines += "\n..."

#             system_prompt = f"""
#                 You are Trucible, a world-class enterprise document specialist with obsessive attention to formatting.

#                 YOUR MISSION:
#                 Take the user's uploaded template and produce an updated version that applies the requested changes 
#                 while preserving **100% of the original visual structure and style**.

#                 NON-NEGOTIABLE RULES:
#                 - Copy the **exact same Markdown formatting**: headings (#, ##), bold (**), lists (- or 1.), tables, spacing, indentation
#                 - Preserve section order, numbering, table column alignment
#                 - Only change content where explicitly requested
#                 - Do NOT add new sections unless asked
#                 - Do NOT remove any sections
#                 - Do NOT add explanations, notes, or commentary
#                 - Output must be valid, clean Markdown

#                 CRITICAL: Your output **MUST start exactly like this** (first few lines of original):
#                 {first_few_lines}
#                 text USER CHANGES TO APPLY:
#                 {changes}

#                 ORIGINAL TEMPLATE (preserve structure exactly):
#                 {raw_text}

#                 **OUTPUT**
#                 ```markdown
#                 Extract the file format in the markdown structure from the file content

                
#                 ```
#                 Now generate the updated document. Start immediately with the title — no intro text.
#             """

#             user_prompt = "Generate the final updated document in clean Markdown format only."
#             prompt = ChatCompletion(system=system_prompt,prev=[],user=user_prompt)
#             filled = llm.run(prompt,MODEL_OPTS,'create_template_mapping',logInDb={"tenant_id": tenant_id, "user_id": user_id})
          
#             if "```markdown" in filled.lower():
#                 parts = filled.lower().split("```markdown", 1)
#                 if len(parts) > 1:
#                     filled = parts[1]
#                 filled = filled.split("```", 1)[0].strip()

#             elif "```" in filled:
#                 parts = filled.split("```")
#                 filled = parts[1] if len(parts) > 1 else parts[0]
#                 filled = filled.strip()
#                 if filled.lower().startswith("markdown"):
#                     filled = filled[8:].strip()

#             # Final safety: ensure it starts like original
#             filled_lines = filled.splitlines()
#             print("\n\n---debug create_template_mapping res---------- ", filled_lines)

#             generated_key = f"generated_doc_{int(datetime.now().timestamp())}"
#             # TangoDao.insertTangoState(
#             #     tenant_id=tenant_id,
#             #     user_id=user_id,
#             #     key=generated_key,
#             #     value=json.dumps({
#             #         "name": f"{template_name} — Generated",
#             #         "content": filled,
#             #         "category": category,
#             #         "generated_at": datetime.utcnow().isoformat()
#             #     }),
#             #     session_id=session_id
#             # )

#             return {
#                 "success": True,
#                 "mode": "document_generated",
#                 "generated_document": filled,
#                 "download_key": generated_key,
#                 "message": f"Here is your {category} using your exact template:",
#                 "template_used": template_name,
#                 "user_satisfied": user_satisfied,
#             }
#         except Exception as e:
#             appLogger.error({"function": "create_template_mapping","error": str(e),"traceback": traceback.format_exc()})
#             return {
#                 "success": False,
#                 "mode": mode,
#                 "generated_document": "Error generating document",
#                 "download_key": None,
#                 "message": f"Error occured: {str(e)}",
#                 "template_used": template_name,
#                 "user_satisfied": False,
#             }



def store_template_file(params:dict) ->dict:
    """
    Upserts a template per (tenant_id, category) with versioning.
    Keeps only one active template per category per tenant.
    """
    try:
        print("--debug store_template_file------ params-----", params)
        params = params.copy()

        tenant_id = params.get("tenant_id")
        created_by_id = params.get("user_id")
        category = params.get("category")
        file_id = params.get("file_id")
        template_structure = params.get("template_structure", {})

        if not tenant_id or not category or not created_by_id:
            raise ValueError("tenant_id, category, and created_by_id are required")

        current_time = datetime.now()

        version_query = f"""
            SELECT 
                id, 
                (template_structure->>'version')::int AS version
            FROM public.tenant_filetemplates
            WHERE tenant_id = {tenant_id}
            AND category ILIKE '%{category}%'
            ORDER BY created_on DESC
            LIMIT 1;
        """
        latest = db_instance.retrieveSQLQueryOld(version_query)  # no params
        print(f"--debug Latest file for {category}------ {latest}")

        if latest:
            latest_id = latest[0]['id']
            latest_version = latest[0]['version']
            next_version = latest_version +1

            # deactivate_query = """
            #     UPDATE public.tenant_filetemplates
            #     SET template_structure =
            #         jsonb_set(
            #             template_structure,
            #             '{is_active}',
            #             'false'::jsonb,
            #             true
            #         )
            #     WHERE tenant_id = %s
            #       AND category = %s
            #       AND (template_structure->>'is_active')::boolean IS TRUE;
            # """
            # db_instance.executeSQLQuery(deactivate_query,(tenant_id, category))
        else:
            next_version = 1

        # Wrap the raw Markdown in a structured dict
        structured_content = {
            "markdown": template_structure.strip(),
            # You can add more fields later: "title", "preview", etc.
        }

        enriched_structure = {
            **structured_content,
            "version": next_version,
            "is_active": True
        }

        insert_query = """
            INSERT INTO public.tenant_filetemplates
            (
                category,
                created_on,
                template_structure,
                created_by_id,
                file_id,
                tenant_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """

        result = db_instance.executeSQLQuery(
            insert_query,
            (
                category,
                current_time,
                json.dumps(enriched_structure),
                # enriched_structure,
                created_by_id,
                file_id,
                tenant_id
            ),
            fetch= 'one'
        )

        template_id = result[0] if result else None

        return {
            "success": True,
            "template_id": template_id,
            "version": next_version,
            "message": f"Template stored (v{next_version}) for category '{category}'"
        }

    except Exception as e:
        appLogger.error({
            "function": "store_template_file",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "tenant_id": params.get("tenant_id"),
            "category": params.get("category")
        })

        return {
            "success": False,
            "message": f"Error storing template file: {str(e)}"
        }



































def convert_raw_doc_text_to_markdown(raw_text: str) -> str:
    """
    Converts raw extracted text from DOC/PDF to clean, structured Markdown
    that preserves the original layout as much as possible.
    """
    lines = raw_text.splitlines()
    markdown_lines = []
    in_table = False
    current_section = None

    for line in lines:
        line = line.rstrip()  # Remove trailing spaces
        stripped = line.strip()

        if not stripped:
            # Multiple empty lines → collapse to one for separation
            if markdown_lines and markdown_lines[-1] != "":
                markdown_lines.append("")
            continue

        # Detect main title (usually first non-empty line, all caps or large)
        if len(markdown_lines) == 0 and len(stripped) > 10 and stripped.isupper():
            markdown_lines.append(f"# {stripped}")
            continue

        # Detect section headers (e.g., "Business Need:", "Project Manager:")
        if ":" in stripped and not stripped.endswith(":") == False:
            # Common pattern: "Label:" followed by value on same/next line
            if stripped.endswith(":"):
                markdown_lines.append(f"## {stripped}")
            else:
                # Label: Value on same line
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    label = parts[0].strip()
                    value = parts[1].strip()
                    if value:
                        markdown_lines.append(f"**{label}:** {value}")
                    else:
                        markdown_lines.append(f"**{label}:**")
                        current_section = label
                else:
                    markdown_lines.append(stripped)
            continue

        # Detect potential table (lines with multiple columns separated by spaces/tabs)
        if re.match(r'^[\w\s–\-]+\t+[\w\s–\-]+', line) or ("|" in line):
            if not in_table:
                in_table = True
                markdown_lines.append("")  # spacer

        if in_table:
            # Simple table detection - split by multiple spaces or tabs
            columns = re.split(r'\t+', line)
            if len(columns) < 2:
                columns = re.split(r'\s{4,}', line)  # 4+ spaces
            if len(columns) >= 2:
                row = " | ".join([col.strip() for col in columns if col.strip()])
                markdown_lines.append(f"| {row} |")
                if len(markdown_lines) == 1 or not markdown_lines[-2].startswith("|"):
                    # Add header separator on second row
                    sep = " | ".join(["---" for col in columns if col.strip()])
                    if len(columns) >= 2:
                        markdown_lines.insert(-1, f"| {sep} |")
            else:
                in_table = False
                markdown_lines.append(stripped)
        else:
            # Paragraph text under a section
            if current_section and not line.startswith(" "):
                markdown_lines.append(stripped)
            else:
                # Indented or continuation
                markdown_lines.append(stripped)

    # Post-cleanup
    md = "\n".join(markdown_lines)
    
    # Collapse excessive blank lines
    md = re.sub(r'\n{3,}', '\n\n', md)
    
    # Fix bold labels without values
    md = re.sub(r'\*\*(.*?):\*\*\n([^\n])', r'**\1:** \2', md)
    
    return md.strip()