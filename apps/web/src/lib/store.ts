'use client';
import {create} from 'zustand';
import {persist} from 'zustand/middleware';
import type {Model,WorkOrder} from './types';
type State={
 step:number;playing:boolean;speed:number;model:Model;assetId:string;scenarioId:string;revealed:boolean;forceOffline:boolean;
 role:'operator'|'technician'|'manager';acknowledged:string[];orders:WorkOrder[];initialized:boolean;demoStep:number|null;
 toast:string|null;crewCount:number;horizon:number;profile:string;jobDelay:number;locked:boolean;tariff:number;capacityFactor:number;hazard:number;
 setStep:(v:number)=>void;setPlaying:(v:boolean)=>void;setSpeed:(v:number)=>void;setModel:(v:Model)=>void;selectAsset:(id:string)=>void;
 setScenario:(id:string)=>void;reveal:()=>void;setOffline:(v:boolean)=>void;setRole:(v:State['role'])=>void;ack:(id:string)=>void;
 initOrders:(orders:WorkOrder[])=>void;updateOrder:(id:string,patch:Partial<WorkOrder>)=>void;addOrder:(order:WorkOrder)=>void;
 setDemo:(v:number|null)=>void;notify:(s:string|null)=>void;setPlanner:(v:Partial<Pick<State,'crewCount'|'horizon'|'profile'|'jobDelay'|'locked'>>)=>void;
 setAssumptions:(v:Partial<Pick<State,'tariff'|'capacityFactor'|'hazard'>>)=>void;reset:()=>void;
};
const initial={step:210,playing:false,speed:1,model:'M2' as Model,assetId:'T-03',scenarioId:'sim-gearbox-drift',revealed:false,forceOffline:false,role:'operator' as const,acknowledged:[] as string[],orders:[] as WorkOrder[],initialized:false,demoStep:null,toast:null,crewCount:2,horizon:7,profile:'balanced',jobDelay:0,locked:false,tariff:3,capacityFactor:.3,hazard:.08};
export const useApp=create<State>()(persist((set)=>({...initial,
 setStep:(step)=>set({step}),setPlaying:(playing)=>set({playing}),setSpeed:(speed)=>set({speed}),setModel:(model)=>set({model}),
 selectAsset:(assetId)=>set({assetId,scenarioId:assetId==='T-03'?'sim-gearbox-drift':'sim-normal-weather',revealed:false}),
 setScenario:(scenarioId)=>set({scenarioId,step:210,revealed:false,playing:false}),reveal:()=>set({revealed:true}),setOffline:(forceOffline)=>set({forceOffline}),setRole:(role)=>set({role}),
 ack:(id)=>set(s=>({acknowledged:[...new Set([...s.acknowledged,id])]})),
 initOrders:(orders)=>set(s=>s.initialized?{}:{orders,initialized:true}),
 updateOrder:(id,patch)=>set(s=>({orders:s.orders.map(o=>o.id===id?{...o,...patch}:o)})),
 addOrder:(order)=>set(s=>({orders:s.orders.some(o=>o.id===order.id)?s.orders:[order,...s.orders]})),
 setDemo:(demoStep)=>set({demoStep}),notify:(toast)=>set({toast}),setPlanner:(v)=>set(v),setAssumptions:(v)=>set(v),
 reset:()=>set({...initial,toast:'Demo reset. Ready for a fresh run.'}),
}),{name:'urjakavach-workspace-v1',partialize:(s)=>({acknowledged:s.acknowledged,orders:s.orders,initialized:s.initialized,role:s.role,crewCount:s.crewCount,horizon:s.horizon,profile:s.profile,tariff:s.tariff,capacityFactor:s.capacityFactor,hazard:s.hazard})}));
