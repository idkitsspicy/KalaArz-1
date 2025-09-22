// --- ALL IMPORTS ---
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import { getFirestore, collection, addDoc, serverTimestamp, getDocs, query, orderBy, limit } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-firestore.js";
import { getStorage, ref, uploadBytes, getDownloadURL } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-storage.js";

// --- FIREBASE CONFIG (optional, for direct Firestore usage if needed) ---
const firebaseConfig = {
  apiKey: "AIzaSyBnBjnfbt2N6LHxBVkSMmEuu_51JI0NHzI",
  authDomain: "artisan-3b8d6.firebaseapp.com",
  databaseURL: "https://artisan-3b8d6-default-rtdb.firebaseio.com",
  projectId: "artisan-3b8d6",
  storageBucket: "artisan-3b8d6.firebasestorage.app",
  messagingSenderId: "63442588763",
  appId: "1:63442588763:web:72a583c2a6a1f26d63db7e",
  measurementId: "G-01922BTK99"
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const storage = getStorage(app);

// --- DOM SELECTORS ---
const $ = s => document.querySelector(s);
const generateBtn = $('#generateBtn');
const publishBtn = $('#publishBtn');
const storyTextarea = $('#story');
const tagsInput = $('#tags');
const statusEl = $('#status');

// --- GET UID FROM FLASK TEMPLATE ---
const userUID = "{{ uid }}";  // Flask injects UID here
console.log("✅ Current user UID:", userUID);

// --- HELPER FUNCTION TO CALL BACKEND WITH UID ---
async function authFetch(url, options = {}) {
  options.headers = options.headers || {};
  // Include UID in headers for backend
  options.headers["X-User-UID"] = userUID;
  return fetch(url, options);
}

// --- GENERATE STORY ---
generateBtn?.addEventListener("click", async () => {
  generateBtn.disabled = true;
  generateBtn.textContent = 'Generating…';
  statusEl.textContent = '';

  try {
    const prompt = $('#prompt')?.value || '';
    if (!prompt) throw new Error("Prompt cannot be empty");

    const resp = await authFetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: prompt, uid: userUID })
    });

    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'Unknown error');

    storyTextarea.value = data.story || '';
    tagsInput.value = (data.tags || []).join(', ');
    statusEl.textContent = 'Story generated!';
  } catch (err) {
    console.error(err);
    statusEl.textContent = '❌ ' + err.message;
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = '⚡ Generate AI Story';
  }
});

// --- PUBLISH STORY ---
publishBtn?.addEventListener("click", async () => {
  publishBtn.disabled = true;
  publishBtn.textContent = 'Publishing…';
  statusEl.textContent = '';

  try {
    const storyText = storyTextarea.value;
    if (!storyText) throw new Error("No story to publish");

    const formData = new FormData();
    formData.append("story", storyText);
    formData.append("uid", userUID);  // Attach UID with the story

    // optional: attach image if available
    const imageFile = $('#image')?.files[0];
    if (imageFile) formData.append("image", imageFile);

    const resp = await fetch('/publish', {
      method: 'POST',
      body: formData
    });

    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || 'Unknown error');

    statusEl.textContent = '✅ Published successfully!';
    storyTextarea.value = '';
    tagsInput.value = '';
  } catch (err) {
    console.error(err);
    statusEl.textContent = '❌ ' + err.message;
  } finally {
    publishBtn.disabled = false;
    publishBtn.textContent = '⬆ Publish';
  }
});
