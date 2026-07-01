from PIL import Image

# Path to your original image
img = Image.open(r"C:\Users\mohan\OneDrive\Pictures\Screenshots\icon.ico.png")

# Resize image (recommended for icon)
img = img.resize((256, 256))

# Save as .ico in the same folder
img.save("my_icon.ico", format='ICO')

print("Icon created successfully!")
