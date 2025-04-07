import streamlit as st
import os
import google.generativeai as genai
import pyperclip
from datetime import datetime
import hashlib
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import base64

# --- Configuration ---
MODEL_NAME = "gemini-1.5-flash"
LOGO_FILE = "writing_assistant_logo.png"  # Change this to your image filename

# Streamlit Page Config
st.set_page_config(
    page_title="✍️ Writing Assistant",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Logo Creation Functions ---
def create_text_logo():
    """Create circular text logo as fallback"""
    img_size = 150
    img = Image.new('RGB', (img_size, img_size), color=(73, 109, 137))
    draw = ImageDraw.Draw(img)
    draw.ellipse((5, 5, img_size-5, img_size-5), outline='white', width=3)
    
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    text = "Writing\nAssistant"
    bbox = draw.textbbox((0, 0), text, font=font, spacing=10)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    position = ((img_size-text_width)/2, (img_size-text_height)/2)
    draw.multiline_text(position, text, font=font, fill='white', align='center', spacing=10)
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return base64.b64encode(img_byte_arr.getvalue()).decode()

def create_logo_from_image():
    """Create logo from custom image file"""
    try:
        img = Image.open(LOGO_FILE).convert("RGBA")
        size = (150, 150)
        
        # Create circular mask
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, *size), fill=255)
        
        # Apply mask
        img = img.resize(size)
        img = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
        img.putalpha(mask)
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return base64.b64encode(img_byte_arr.getvalue()).decode()
    except Exception as e:
        st.warning(f"Custom logo not found/loaded: {str(e)}. Using text logo.")
        return create_text_logo()

logo_base64 = create_logo_from_image()

# --- Custom CSS ---
st.markdown(f"""
<style>
    .logo-container {{
        display: flex;
        justify-content: center;
        margin-bottom: 1.5rem;
    }}
    .logo-img {{
        width: 150px;
        height: 150px;
        border-radius: 50%;
        object-fit: cover;
        border: 3px solid #4e8cff;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }}
    .fixed-input {{
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        padding: 1rem;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        z-index: 100;
    }}
    .status-bar {{
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 1rem;
        background: #f8f9fa;
        border-top: 1px solid #e9ecef;
        font-size: 0.8rem;
    }}
    .history-item {{
        padding: 0.5rem;
        margin: 0.2rem 0;
        border-radius: 5px;
        cursor: pointer;
        transition: all 0.2s;
    }}
    .history-item:hover {{
        background-color: #f0f2f6;
    }}
    .home-btn {{
        position: absolute;
        top: 10px;
        right: 10px;
        z-index: 1000;
    }}
</style>
""", unsafe_allow_html=True)

# --- Initialize Gemini ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Please set your Google API key in environment variables or Streamlit secrets")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# --- Session State ---
if "current_mode" not in st.session_state:
    st.session_state.current_mode = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "draft" not in st.session_state:
    st.session_state.draft = ""
if "history" not in st.session_state:
    st.session_state.history = []
if "processing" not in st.session_state:
    st.session_state.processing = False

# --- Helper Functions ---
def generate_unique_key(text, prefix=""):
    return f"{prefix}_{hashlib.md5(text.encode()).hexdigest()[:8]}"

def count_words(text):
    return len(text.split()) if text else 0

def add_to_history(input_text, output_text, mode):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.history.insert(0, {
        "input": input_text,
        "output": output_text,
        "mode": mode,
        "timestamp": timestamp
    })
    st.session_state.history = st.session_state.history[:20]

def reset_to_home():
    st.session_state.current_mode = None
    st.session_state.messages = []
    st.session_state.draft = ""
    st.rerun()

# --- System Prompts ---
GRAMMAR_SYSTEM_PROMPT = """
You are a professional grammar editor. Analyze text for:
1. Grammar/syntax errors
2. Punctuation mistakes 
3. Sentence structure improvements
4. Word choice enhancements

Return corrected text with minimal changes.
"""

CONTENT_SYSTEM_PROMPT = """
You are a professional content creator. Generate well-structured content with:
1. Clear introduction
2. Organized body paragraphs
3. Strong conclusion
"""

SYNONYM_SYSTEM_PROMPT = """
You are a vocabulary enhancer. Provide:
1. Standard Synonyms
2. Contextual Variations
3. Example Sentences
"""

# --- UI Components ---
def show_home_button():
    if st.session_state.current_mode is not None:
        if st.button("🏠 Home", key="home_button", help="Return to home page"):
            reset_to_home()

def show_status_bar():
    current_time = datetime.now().strftime("%H:%M:%S")
    word_count = count_words(st.session_state.draft)
    mode = st.session_state.current_mode.capitalize() if st.session_state.current_mode else "Select Mode"
    
    st.markdown(f"""
    <div class="status-bar">
        <span>🕒 {current_time} | 📝 {word_count} words | 🛠️ {mode}</span>
    </div>
    """, unsafe_allow_html=True)

def show_grammar_tools():
    with st.expander("🛠️ Advanced Grammar Tools", expanded=True):
        cols = st.columns(4)
        tools = [
            ("Check Punctuation", "Check punctuation in:\n{text}"),
            ("Improve Clarity", "Improve clarity of:\n{text}"),
            ("Simplify Text", "Simplify this text:\n{text}"),
            ("Formal Tone", "Make this more formal:\n{text}")
        ]
        
        for idx, (name, template) in enumerate(tools):
            with cols[idx]:
                if st.button(name, key=generate_unique_key(f"grammar_{name}")):
                    st.session_state.draft = template.format(text=st.session_state.draft)
                    st.rerun()

def show_content_templates():
    with st.expander("📋 Content Templates", expanded=True):
        templates = [
            {"name": "Blog Post", "prompt": "Write a blog post about: [topic]"},
            {"name": "Business Email", "prompt": "Write a professional email about: [subject]"},
            {"name": "Report", "prompt": "Write a report on: [topic]"}
        ]
        
        for template in templates:
            if st.button(template["name"], key=generate_unique_key(f"template_{template['name']}")):
                st.session_state.draft = template["prompt"]
                st.rerun()

def show_history_sidebar():
    with st.sidebar:
        st.header("📚 Task History")
        if not st.session_state.history:
            st.info("No history yet. Submit some text to see history here.")
        
        for idx, item in enumerate(st.session_state.history):
            with st.container():
                if st.button(
                    f"{item['mode'].capitalize()} - {item['timestamp']}",
                    key=generate_unique_key(f"history_{idx}_{item['input']}"),
                    use_container_width=True,
                    help=f"Replay: {item['input'][:50]}..."
                ):
                    st.session_state.draft = item["input"]
                    st.session_state.current_mode = item["mode"]
                    st.rerun()
                
                if st.button(
                    "📋",
                    key=generate_unique_key(f"copy_history_{idx}_{item['output']}"),
                    help="Copy output to clipboard"
                ):
                    pyperclip.copy(item["output"])
                    st.toast("✓ Copied to clipboard!")

def show_mode_selection():
    if logo_base64:
        st.markdown(f"""
        <div class="logo-container">
            <img src="data:image/png;base64,{logo_base64}" class="logo-img">
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
        <h1 style="font-size: 2.5rem; color: #2c3e50;">✍️ Writing Assistant</h1>
        <p style="font-size: 1.1rem; color: #7f8c8d;">POWERED BY TECH PIXEL</p>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    modes = [
        ("Grammar Correction", "🔍", "#ff6b6b"),
        ("Content Creation", "✏️", "#4ecdc4"),
        ("Synonym Suggestions", "📚", "#ffbe76")
    ]
    
    for idx, (title, icon, color) in enumerate(modes):
        with cols[idx]:
            if st.button(
                f"{icon} {title}",
                key=generate_unique_key(f"mode_{title}"),
                use_container_width=True,
                help=f"Switch to {title} mode"
            ):
                st.session_state.current_mode = title.split()[0].lower()
                st.session_state.messages = [{
                    "role": "assistant", 
                    "content": f"I'm your {title} assistant. How can I help?"
                }]
                st.rerun()

def show_chat_interface():
    show_home_button()
    
    if st.session_state.current_mode == "grammar":
        show_grammar_tools()
    elif st.session_state.current_mode == "content":
        show_content_templates()
    
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                if st.button(
                    "📋", 
                    key=generate_unique_key(f"copy_{idx}_{msg['content']}"),
                    help="Copy to clipboard"
                ):
                    pyperclip.copy(msg['content'])
                    st.toast("✓ Copied to clipboard!")
    
    st.markdown('<div class="fixed-input">', unsafe_allow_html=True)
    
    draft = st.text_area(
        "Your text:", 
        value=st.session_state.draft, 
        key=generate_unique_key("draft_input"),
        label_visibility="collapsed",
        placeholder="Type or paste your text here...",
        height=150
    )
    
    if draft != st.session_state.draft:
        st.session_state.draft = draft
    
    if st.button(
        "Submit", 
        type="primary", 
        key=generate_unique_key("submit_button"),
        use_container_width=True, 
        disabled=st.session_state.processing
    ):
        if st.session_state.draft.strip():
            process_submission()
    
    show_status_bar()
    st.markdown('</div>', unsafe_allow_html=True)

def process_submission():
    st.session_state.processing = True
    try:
        if st.session_state.current_mode == "grammar":
            response = model.generate_content(f"{GRAMMAR_SYSTEM_PROMPT}\n\n{st.session_state.draft}")
        elif st.session_state.current_mode == "content":
            response = model.generate_content(f"{CONTENT_SYSTEM_PROMPT}\n\n{st.session_state.draft}")
        else:
            response = model.generate_content(f"{SYNONYM_SYSTEM_PROMPT}\n\n{st.session_state.draft}")
        
        st.session_state.messages.extend([
            {"role": "user", "content": st.session_state.draft},
            {"role": "assistant", "content": response.text}
        ])
        
        add_to_history(st.session_state.draft, response.text, st.session_state.current_mode)
        st.session_state.draft = ""
        st.toast("✔ Task completed successfully!")
        
    except Exception as e:
        st.error(f"Error processing request: {str(e)}")
    finally:
        st.session_state.processing = False
        st.rerun()

# --- Main App ---
def main():
    show_history_sidebar()
    
    if st.session_state.current_mode is None:
        show_mode_selection()
    else:
        show_chat_interface()

if __name__ == "__main__":
    main()