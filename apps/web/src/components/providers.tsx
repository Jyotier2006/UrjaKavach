'use client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {useState,useEffect} from 'react';
import {Shell} from './shell';
export function Providers({children}:{children:React.ReactNode}){const [client]=useState(()=>new QueryClient());useEffect(()=>{if('serviceWorker'in navigator && process.env.NODE_ENV==='production')navigator.serviceWorker.register('/sw.js').catch(()=>{});},[]);return <QueryClientProvider client={client}><Shell>{children}</Shell></QueryClientProvider>;}
