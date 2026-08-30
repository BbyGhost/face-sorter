import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const people = [{name:'Unassigned', count:0, color:'#596273'}, {name:'Alice', count:128, color:'#9c73ff'}, {name:'Jordan', count:84, color:'#47c4a6'}, {name:'Unknown', count:34, color:'#f2a85b'}];
function App() {
  const [folder, setFolder] = useState(''); const [status, setStatus] = useState('Ready to scan');
  async function choose() { const selected = await window.desktop?.pickFolder(); if (selected) { setFolder(selected); setStatus('Folder selected — ready to scan'); } }
  function scan() { if (!folder) return setStatus('Choose a photo library first'); setStatus('Scanner is ready. Start the Python service to process this library.'); }
  return <main><aside><div className="brand"><span>◉</span> Face Sorter</div><nav><a className="active">Overview</a><a>People</a><a>Exports</a><a>Settings</a></nav><div className="privacy">⌁ Local-only processing<br/><small>Your photos never leave this device.</small></div></aside>
  <section><header><div><p className="eyebrow">PHOTO LIBRARY</p><h1>Organize memories by the people in them.</h1><p className="sub">Scan, identify, and sort your photos privately on this computer.</p></div><button className="ghost">⚙ Settings</button></header>
  <div className="hero"><div><p className="eyebrow">GET STARTED</p><h2>Choose your photo library</h2><p>{folder || 'Select a folder containing your photos. Subfolders are included.'}</p><div className="actions"><button onClick={choose}>Choose folder</button><button onClick={scan} className="secondary">Start scan</button></div><p className="status">● {status}</p></div><div className="orb">⌁</div></div>
  <div className="section-title"><h2>People</h2><button className="link">Manage people →</button></div><div className="people">{people.map(p=><article key={p.name}><div className="avatar" style={{background:p.color}}>{p.name[0]}</div><strong>{p.name}</strong><span>{p.count} photos</span></article>)}</div>
  <div className="notice"><strong>Before your first scan</strong><p>Install the Python recognition service from <code>backend/requirements.txt</code>, then run <code>python backend/service.py</code>. The service stays on your device and stores its index locally.</p></div>
  </section></main>;
}
createRoot(document.getElementById('root')).render(<App/>);
