from flask import Flask, render_template, request, jsonify
import os, time
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration, AutoTokenizer, AutoModelForSeq2SeqLM
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

device = "cuda" if torch.cuda.is_available() else "cpu"

# BLIP descriptive caption
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").to(device)

# FLAN-T5 for creative captioning
tokenizer_style = AutoTokenizer.from_pretrained("google/flan-t5-base")
model_style = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-base").to(device)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def generate_caption(image):
    """Descriptive caption using BLIP."""
    inputs = processor(images=image, return_tensors="pt").to(device)
    out = blip_model.generate(**inputs, max_new_tokens=50)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption

def style_caption(base_caption, style="trendy"):
    """Generate creative, fun, poetic, Instagram/Twitter style caption with emojis and hashtags."""
    prompt = f"""
You are a professional social media caption writer. Rewrite the descriptive caption below into a creative, fun, poetic, Instagram/Twitter-style caption with flair. Include emojis and trendy hashtags.  

Descriptive caption: "{base_caption}"  
Caption:
"""
    inputs = tokenizer_style(prompt, return_tensors="pt").to(device)
    out = model_style.generate(
        **inputs,
        max_length=100,
        do_sample=True,
        temperature=1.5,
        top_p=0.95,
        num_return_sequences=1
    )
    caption = tokenizer_style.decode(out[0], skip_special_tokens=True)
    return caption

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400

        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            image = Image.open(filepath).convert('RGB')

            start_time = time.time()
            base_caption = generate_caption(image)
            # Choose style based on user (optional: default "trendy")
            style = request.form.get('style', 'trendy')
            final_caption = style_caption(base_caption, style)
            processing_time = time.time() - start_time

            try:
                os.remove(filepath)
            except:
                pass

            return jsonify({
                'success': True,
                'caption': final_caption,
                'processing_time': f"{processing_time:.2f}s"
            })

        except Exception as e:
            return jsonify({'error': str(e), 'message': 'Error processing image'}), 500

    return render_template('index.html')

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("✓ Server running at http://localhost:5000")
    app.run(debug=True, use_reloader=False)
