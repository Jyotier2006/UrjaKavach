'use client';
export default function Error({reset}:{error:Error;reset:()=>void}){return <div className="empty-state"><h2>This view needs a fresh start.</h2><p>Your saved work orders remain on this device.</p><button className="button primary" onClick={reset}>Try again</button></div>;}
