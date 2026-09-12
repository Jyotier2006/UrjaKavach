'use client';
import {useEffect} from 'react';
import {Play,Pause,Flag,RotateCcw} from 'lucide-react';
import {useApp} from '@/lib/store';
import {relativeTime} from '@/lib/data';
import type {Scenario} from '@/lib/types';
export function Replay({scenario}:{scenario:Scenario}){const {step,playing,speed,model,setPlaying,setStep,setSpeed}=useApp();
 useEffect(()=>{if(!playing)return;const id=setInterval(()=>{const s=useApp.getState();if(s.step>=scenario.data.length-1){s.setPlaying(false);return;}s.setStep(Math.min(s.step+speed,scenario.data.length-1));},500);return()=>clearInterval(id);},[playing,speed,scenario.data.length]);
 const alarm=scenario.alarms[model];
 return <div className="replay-bar"><button className="play-button" aria-label={playing?'Pause replay':'Play replay'} onClick={()=>setPlaying(!playing)}>{playing?<Pause size={16}/>:<Play size={16}/>}</button><span className="replay-time">{relativeTime(step)}</span><div className="timeline-input"><input type="range" aria-label="Replay timeline" min={0} max={scenario.data.length-1} value={step} onChange={e=>{setStep(+e.target.value);setPlaying(false);}}/>{alarm!==null&&<span className="alarm-tick" style={{left:`${alarm/(scenario.data.length-1)*100}%`}} title="Alarm threshold crossed"/>}</div><button className="button secondary small jump-button" disabled={alarm===null} onClick={()=>{setStep(alarm??0);setPlaying(false);}}><Flag size={14}/>Jump to warning</button><select aria-label="Replay speed" value={speed} onChange={e=>setSpeed(+e.target.value)}><option value={1}>1×</option><option value={4}>4×</option><option value={12}>12×</option></select><button className="icon-button replay-reset" aria-label="Restart replay" onClick={()=>{setStep(0);setPlaying(false);}}><RotateCcw size={15}/></button></div>;
}
