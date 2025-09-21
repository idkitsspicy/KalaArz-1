// --- ALL IMPORTS ---
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import {
    getFirestore, collection, addDoc, serverTimestamp, getDocs, query, orderBy, limit
} from "https://www.gstatic.com/firebasejs/11.0.1/firebase-firestore.js";
import {
    getStorage, ref, uploadBytes, getDownloadURL
} from "https://www.gstatic.com/firebasejs/11.0.1/firebase-storage.js";
import {
    getAuth, onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

// --- FIREBASE CONFIG ---
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
const auth = getAuth(app);
let currentUser = null;

onAuthStateChanged(auth, (user) => {
    if (user) {
        console.log("✅ Logged in as:", user.uid);
        currentUser = user;
    } else {
        console.log("❌ No user logged in");
        currentUser = null;
    }
});

// Debug: make it visible in DevTools
window.auth = auth;

// --- HELPERS ---
const $ = s => document.querySelector(s);

function escapeHtml(s) {
    if (!s) return '';
    return s.replace(/[&<>"']/g, m => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;" }[m]));
}

function getFormDataObj() {
    const fm = $('#craftForm');
    const fd = new FormData(fm);
    const obj = {};
    for (const [k, v] of fd.entries()) obj[k] = v;
    return obj;
}

// --- DOM ELEMENTS ---
const postsList = $('#postsList');
const postModal = $('#postModal');

// --- EVENTS ---
document.addEventListener('DOMContentLoaded', () => {
    $('#generateBtn').addEventListener('click', onGenerate);
    $('#publishBtn').addEventListener('click', onPublish);
    $('#cancelBtn').addEventListener('click', () => $('#results').classList.add('hidden'));

    $('#postModal .close').onclick = () => postModal.style.display = 'none';
    window.onclick = e => { if (e.target === postModal) postModal.style.display = 'none'; };

    loadPosts();
});

// --- ADD POST CARD ---
function addPostCard(post) {
    const card = document.createElement('div');
    card.className = 'post-card';
    card.innerHTML = `
        ${post.imageUrl ? `<img src="${post.imageUrl}" alt="${escapeHtml(post.productName)}">` : ''}
        <div class="post-card-body">
            <h3>${escapeHtml(post.productName)}</h3>
            <p>By ${escapeHtml(post.name)} from ${escapeHtml(post.place)}</p>
        </div>
    `;
    card.addEventListener('click', () => openPostModal(post));
    postsList.prepend(card);
}

function openPostModal(post) {
    $('#modalTitle').textContent = post.productName;
    $('#modalStory').innerHTML = `<strong>Story:</strong> ${post.story || ''}`;
    $('#modalTags').textContent = post.tags ? post.tags.join(', ') : '';
    const img = $('#modalImage');
    if (post.imageUrl) {
        img.src = post.imageUrl;
        img.alt = post.productName;
        img.style.display = 'block';
    } else img.style.display = 'none';
    postModal.style.display = 'block';
}

// --- GENERATE STORY (calls backend AI) ---
async function onGenerate() {
    const btn = $('#generateBtn');
    btn.disabled = true; btn.textContent = 'Generating…';
    $('#status').textContent = '';

    try {
        const payload = getFormDataObj();
        if (!payload.name || !payload.productName) {
            alert('Fill in Name and Product Name!');
            return;
        }
        const resp = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (!data.ok) throw new Error(data.error || 'Unknown error');

        $('#story').value = data.story || '';
        $('#tags').value = (data.tags || []).join(', ');
        $('#results').classList.remove('hidden');
    } catch (err) {
        alert('Generation failed: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '⚡ Generate AI Story';
    }
}

// --- PUBLISH TO FIRESTORE & STORAGE (Auth aware) ---
async function onPublish() {
    const btn = $('#publishBtn');
    btn.disabled = true; btn.textContent = 'Publishing…';
    const statusEl = $('#status');
    statusEl.textContent = '';

    const craftForm = $('#craftForm');

    if (!currentUser) {
        alert("⚠️ Please login as an NGO to publish.");
        btn.disabled = false;
        btn.textContent = '⬆ Publish';
        return;
    }

    try {
        const imageFile = craftForm.image.files[0];
        let imageUrl = null;

        if (imageFile) {
            statusEl.textContent = 'Uploading image...';
            const fileName = `${Date.now()}-${imageFile.name}`;
            console.log("User UID (auth):", currentUser.uid);
            console.log("Upload path:", `posts/${currentUser.uid}/${fileName}`);
            const storageRef = ref(storage, `posts/${currentUser.uid}/${fileName}`);
            const uploadTask = await uploadBytes(storageRef, imageFile);
            imageUrl = await getDownloadURL(uploadTask.ref);
            statusEl.textContent = 'Image uploaded!';
        }

        const postData = {
            ngoId: currentUser.uid, // 🔑 attach Auth UID
            name: craftForm.name.value,
            age: craftForm.age.value,
            place: craftForm.place.value,
            productName: craftForm.productName.value,
            craftType: craftForm.craftType.value,
            materials: craftForm.materials.value,
            inspiration: craftForm.inspiration.value,
            audience: craftForm.audience.value,
            language: craftForm.language.value,
            tone: craftForm.tone.value,
            story: $('#story').value,
            tags: $('#tags').value.split(',').map(t => t.trim()).filter(t => t),
            imageUrl,
            createdAt: serverTimestamp()
        };

        statusEl.textContent = 'Saving data...';
        const docRef = await addDoc(collection(db, 'posts'), postData);
        statusEl.textContent = 'Published!';

        addPostCard({ ...postData, id: docRef.id });
        $('#results').classList.add('hidden');
        craftForm.reset();
    } catch (err) {
        console.error(err);
        statusEl.textContent = 'Error: ' + err.message;
    } finally {
        btn.disabled = false;
        btn.textContent = '⬆ Publish';
    }
}

// --- LOAD POSTS FROM FIRESTORE ---
async function loadPosts() {
    postsList.innerHTML = 'Loading posts...';
    try {
        const postsRef = collection(db, 'posts');
        const q = query(postsRef, orderBy('createdAt', 'desc'), limit(20));
        const snapshot = await getDocs(q);

        postsList.innerHTML = '';
        if (snapshot.empty) {
            postsList.textContent = 'No posts yet — publish the first story!';
            return;
        }
        snapshot.forEach(doc => addPostCard({ id: doc.id, ...doc.data() }));
    } catch (err) {
        console.error(err);
        postsList.textContent = 'Error loading posts.';
    }
}



