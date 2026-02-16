# Filename: take_picture.py (save it under the /src folder in your repo)

from pylablib.devices import Thorlabs

def main():
    try:
        # Connect to your camera using serial number (change if needed)
        cam = Thorlabs.ThorlabsTLCamera(serial="33012")

        print("Camera connected!")

        # Take a single picture
        image = cam.snap()
        print("Picture taken!")

        # Save the image as PNG in the current folder
        output_file = "C:/Users/Monster/Desktop/tez/sample_image.png"
        cam.save_image(image, output_file)
        print(f"Image saved as {output_file}")

        # Always close the camera connection!
        cam.close()
        print("Camera connection closed.")

    except Exception as e:
        print("Error: Could not connect to camera or take picture.")
        print("Details:", e)

if __name__ == "__main__":
    main()

