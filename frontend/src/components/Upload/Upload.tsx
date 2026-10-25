import React, { useState } from 'react';
import axios from 'axios';
import { UploadCloud, FileText } from "lucide-react";

interface UploadProps {
  onUploadSuccess: () => void;
}

export default function UploadCSV({ onUploadSuccess }: UploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) { 
      setMessage("Please select a file first."); 
      return; 
    }
    
    setIsLoading(true);
    setMessage("Uploading and analyzing data...");
    const formData = new FormData();
    formData.append("file", file);

    try {
      await axios.post("http://127.0.0.1:5000/upload", formData);
      setMessage("Analysis complete!");
      onUploadSuccess(); 
    } catch (err) {
      console.error("An error occurred during the request:", err);
      let userMessage = "An unexpected error occurred. Please try again.";
      if (axios.isAxiosError(err)) {
        if (err.response) {
          console.error("Backend Error Response:", err.response.data);
          const serverError = err.response.data?.error || `Request failed with status code ${err.response.status}`;
          userMessage = `Server Error: ${serverError}. Please check the backend logs for details.`;
        } else if (err.request) {
          console.error("No response received from the server:", err.request);
          userMessage = "Could not connect to the server. Is the backend running?";
        } else { 
          userMessage = `Request setup error: ${err.message}`; 
        }
      }
      setMessage(userMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100 font-sans">
      <div className="w-full max-w-lg p-8 space-y-8 bg-white rounded-xl shadow-2xl">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Churn Prediction</h2>
          <p className="mt-2 text-sm text-gray-600">Upload your customer data to get started</p>
        </div>
        <form onSubmit={handleUpload} className="space-y-6">
          <label htmlFor="file-upload" className="relative cursor-pointer bg-white rounded-md font-medium text-indigo-600 hover:text-indigo-500">
            <div className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-gray-300 rounded-lg text-center hover:border-indigo-400 transition-colors">
              <UploadCloud className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-600"><span className="font-semibold">Click to upload</span> or drag and drop</p>
              <p className="text-xs text-gray-500">CSV file up to 10MB</p>
              {file && (
                <div className="mt-4 flex items-center text-sm font-medium text-green-600">
                  <FileText className="h-5 w-5 mr-2" />{file.name}
                </div>
              )}
            </div>
            <input 
              id="file-upload" 
              name="file-upload" 
              type="file" 
              className="sr-only" 
              accept=".csv" 
              onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)} 
            />
          </label>
          <button 
            type="submit" 
            disabled={isLoading || !file} 
            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:bg-indigo-300 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Processing...' : 'Upload and Predict'}
          </button>
        </form>
        {message && <p className="text-center text-sm text-red-600 mt-4">{message}</p>}
      </div>
    </div>
  );
}
