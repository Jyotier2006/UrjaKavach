'use client';
import {useQuery} from '@tanstack/react-query';
import {useApp} from './store';
import type {Bundle,Scenario,LossResult,Schedule,Solar} from './types';
export const API_URL=(process.env.NEXT_PUBLIC_API_URL||'').replace(/\/$/,'');
export function useArtifact<T>(name:string){return useQuery<T>({queryKey:['artifact',name],queryFn:async()=>{const r=await fetch(`/demo/${name}.json`);if(!r.ok)throw new Error('The demo bundle could not be loaded. Check the connection and try again.');return r.json();},staleTime:Infinity,retry:1});}
export const useBundle=()=>useArtifact<Bundle>('bundle');
export const useScenarios=()=>useArtifact<Scenario[]>('scenarios');
export const useSolar=()=>useArtifact<Solar>('solar');
export const usePlans=()=>useArtifact<Record<string,Schedule>>('plans');
export const useLosses=()=>useArtifact<Record<string,LossResult>>('loss-catalog');
export function useApiStatus(){const offline=useApp(s=>s.forceOffline);return useQuery({queryKey:['api-status',offline],queryFn:async()=>{if(!API_URL||offline)return false;try{const r=await fetch(`${API_URL}/health`,{signal:AbortSignal.timeout(2500)});return r.ok;}catch{return false;}},staleTime:15000,refetchInterval:30000});}
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{if(!API_URL)throw new Error('Connect the Python API to use this live action.');const r=await fetch(API_URL+path,{method,headers:body instanceof FormData?{}:{'Content-Type':'application/json'},body:body instanceof FormData?body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(12000)});if(!r.ok){const e=await r.json().catch(()=>({detail:'API request failed'}));throw new Error(typeof e.detail==='string'?e.detail:'Check the submitted values');}return r.json();}
export function downloadJson(name:string,data:unknown){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);}
export const inr=(v:number,compact=true)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0,...(compact?{notation:'compact' as const,maximumFractionDigits:1}:{})}).format(v);
export const number=(v:number,digits=0)=>new Intl.NumberFormat('en-IN',{maximumFractionDigits:digits}).format(v);
export function relativeTime(step:number){const mins=step*10;return `Day ${Math.floor(mins/1440)+1} · ${String(Math.floor(mins%1440/60)).padStart(2,'0')}:${String(mins%60).padStart(2,'0')}`;}
export function assetStatus(id:string,step:number,alarmIndex:number|null,fallback:string){if(id!=='T-03')return fallback;return alarmIndex!==null&&step>=alarmIndex?'Warning':step>=100?'Watch':'Healthy';}
