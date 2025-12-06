
// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getStorage } from "firebase/storage"; // Import Firebase Storage

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyCaO3ZUVSpy-X-IuYQ5jKC4H4lOuB3PPys",
  authDomain: "intervieu-7a3bb.firebaseapp.com",
  projectId: "intervieu-7a3bb",
  storageBucket: "intervieu-7a3bb.appspot.com", // Corrected storage bucket if needed
  messagingSenderId: "28058838137",
  appId: "1:28058838137:web:56314057e5a5f64ef760a8",
  measurementId: "G-4GKY9PH8ZB"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const storage = getStorage(app); // Initialize and export Firebase Storage
