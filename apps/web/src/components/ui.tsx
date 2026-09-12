'use client';
import {AlertTriangle,CheckCircle2,Eye,Info,LoaderCircle,ShieldAlert} from 'lucide-react';
import type {ReactNode} from 'react';
export function Status({value}:{value:string}){const Icon=['Warning','High'].includes(value)?AlertTriangle:['Critical'].includes(value)?ShieldAlert:['Healthy','Completed','Resolved'].includes(value)?CheckCircle2:Eye;return <span className={`status status-${value.toLowerCase().replaceAll(' ','-')}`}><Icon size={13}/>{value}</span>;}
export function PageHeading({title,description,actions}:{title:string;description:string;actions?:ReactNode}){return <div className="page-heading"><div><h1>{title}</h1><p>{description}</p></div>{actions&&<div className="page-actions">{actions}</div>}</div>;}
export function Panel({title,subtitle,action,children,className=''}:{title?:string;subtitle?:string;action?:ReactNode;children:ReactNode;className?:string}){return <section className={`panel ${className}`}>{title&&<header className="panel-heading"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</header>}{children}</section>;}
export function Notice({children,tone='muted'}:{children:ReactNode;tone?:'muted'|'warning'|'green'}){return <div className={`notice notice-${tone}`}><Info size={16}/><div>{children}</div></div>;}
export function Loading(){return <div className="loading"><LoaderCircle className="spin" size={24}/><p>Opening your operations workspace…</p></div>;}
export function ErrorState({message,retry}:{message:string;retry?:()=>void}){return <div className="empty-state"><AlertTriangle size={30}/><h2>We couldn’t load this view</h2><p>{message}</p>{retry&&<button className="button primary" onClick={retry}>Try again</button>}</div>;}
export function Stat({label,value,detail,icon}:{label:string;value:string;detail?:string;icon?:ReactNode}){return <div className="stat">{icon&&<span className="stat-icon">{icon}</span>}<div><span className="stat-label">{label}</span><strong>{value}</strong>{detail&&<span className="stat-detail">{detail}</span>}</div></div>;}
export function Provenance({source='Simulated'}:{source?:string}){return <span className="provenance"><span/>{source}</span>;}
