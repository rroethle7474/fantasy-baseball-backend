import requests
import os

def test_upload():
    """Test the upload endpoint with a sample CSV file."""
    url = 'http://localhost:5000/api/upload'
    
    # Path to the sample CSV file
    file_path = os.path.join(os.path.dirname(__file__), 'sample_data.csv')
    
    # Prepare the files and data for the request
    files = {'file': open(file_path, 'rb')}
    data = {'name': 'Test Model', 'description': 'Test model for fantasy baseball data'}
    
    # Make the request
    response = requests.post(url, files=files, data=data)
    
    # Close the file
    files['file'].close()
    
    # Print the response
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == '__main__':
    test_upload() 