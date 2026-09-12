'use client';
import {Canvas,useFrame} from '@react-three/fiber';
import {OrbitControls,Html,OrthographicCamera} from '@react-three/drei';
import {useCallback,useEffect,useLayoutEffect,useMemo,useRef,useState,Component} from 'react';
import * as THREE from 'three';
import {useApp} from '@/lib/store';
import type {Asset} from '@/lib/types';

// Late-afternoon key light. Slightly warm, so the pale towers pick up a tint and read as lit rather than flat.
const KEY_LIGHT='#fff3dd';
const SKY='#dbe6ef';
const GROUND_BOUNCE='#9aa878';

/** Soft blurred blob under the site, so the parcel sits on the sky instead of floating over it. */
function GroundShadow(){
  const texture=useMemo(()=>{
    const canvas=document.createElement('canvas');
    canvas.width=canvas.height=128;
    const ctx=canvas.getContext('2d');
    if(!ctx)return null;
    const gradient=ctx.createRadialGradient(64,64,4,64,64,62);
    gradient.addColorStop(0,'rgba(60,74,58,0.42)');
    gradient.addColorStop(.55,'rgba(60,74,58,0.16)');
    gradient.addColorStop(1,'rgba(60,74,58,0)');
    ctx.fillStyle=gradient;ctx.fillRect(0,0,128,128);
    const t=new THREE.CanvasTexture(canvas);
    t.colorSpace=THREE.SRGBColorSpace;
    return t;
  },[]);
  if(!texture)return null;
  return <mesh rotation={[-Math.PI/2,0,0]} position={[1.5,-1.12,2]} renderOrder={-1}>
    <planeGeometry args={[54,44]}/>
    <meshBasicMaterial map={texture} transparent depthWrite={false}/>
  </mesh>;
}

/** Pointer feedback shared by every clickable asset: a hand cursor and a highlight while hovered. */
function useHover(){
  const [hovered,setHovered]=useState(false);
  useEffect(()=>{
    if(!hovered)return;
    document.body.style.cursor='pointer';
    return()=>{document.body.style.cursor='';};
  },[hovered]);
  const bind={
    onPointerOver:(e:{stopPropagation:()=>void})=>{e.stopPropagation();setHovered(true);},
    onPointerOut:()=>setHovered(false),
  };
  return{hovered,bind};
}

function Blade(){
  const shape=useMemo(()=>{const s=new THREE.Shape();s.moveTo(-.1,.15);s.lineTo(-.22,1);s.quadraticCurveTo(-.12,2.1,.05,3.05);s.lineTo(.14,3.1);s.lineTo(.2,1.05);s.lineTo(.14,.2);s.closePath();return s;},[]);
  return <mesh castShadow><extrudeGeometry args={[shape,{depth:.045,bevelEnabled:true,bevelSegments:1,steps:1,bevelSize:.025,bevelThickness:.025}]}/><meshStandardMaterial color="#fbfbf5" roughness={.42} metalness={.05}/></mesh>;
}

function Turbine({asset,onSelect,warning}:{asset:Asset;onSelect:(id:string)=>void;warning:boolean}){
  const rotor=useRef<THREE.Group>(null);
  const nacelle=useRef<THREE.Group>(null);
  const playing=useApp(s=>s.playing);
  const speed=useApp(s=>s.speed);
  const [reduced,setReduced]=useState(false);
  const {hovered,bind}=useHover();
  useEffect(()=>{setReduced(window.matchMedia('(prefers-reduced-motion: reduce)').matches);},[]);
  useFrame((state,delta)=>{
    if(reduced)return;
    if(rotor.current&&playing)rotor.current.rotation.z-=delta*(.55+asset.power_kw/2500)*Math.min(speed,4);
    // A slow yaw drift keeps the field alive without implying the turbines are tracking anything real.
    if(nacelle.current)nacelle.current.rotation.y=-.3+Math.sin(state.clock.elapsedTime*.12+asset.position[0])*.08;
  });
  const tint=hovered?'#ffffff':'#f6f6ec';
  const glow=hovered?.32:0;
  return <group position={[asset.position[0],.04,asset.position[1]]} onClick={e=>{e.stopPropagation();onSelect(asset.id);}} {...bind}>
    <mesh receiveShadow castShadow><cylinderGeometry args={[.85,.95,.2,22]}/><meshStandardMaterial color="#dcdccc" roughness={.9}/></mesh>
    <mesh position={[0,3.65,0]} castShadow><cylinderGeometry args={[.18,.34,7.3,14]}/><meshStandardMaterial color={tint} roughness={.5} metalness={.08} emissive="#ffd9a8" emissiveIntensity={glow}/></mesh>
    <group ref={nacelle} position={[0,7.25,0]} rotation={[0,-.3,0]}>
      <mesh position={[0,.1,-.32]} castShadow><boxGeometry args={[.64,.65,1.7]}/><meshStandardMaterial color={tint} roughness={.45} emissive="#ffd9a8" emissiveIntensity={glow}/></mesh>
      <group ref={rotor} position={[0,.07,.62]} rotation={[0,0,asset.position[0]*.5]}>
        <mesh castShadow rotation={[Math.PI/2,0,0]}><coneGeometry args={[.3,.65,18]}/><meshStandardMaterial color="#eff0e7" roughness={.4}/></mesh>
        {[0,1,2].map(i=><group key={i} rotation={[0,0,i*Math.PI*2/3]}><Blade/></group>)}
      </group>
    </group>
    {warning&&<WarningRing/>}
    {hovered&&!warning&&<mesh rotation={[-Math.PI/2,0,0]} position={[0,.16,0]}><ringGeometry args={[1.15,1.32,44]}/><meshBasicMaterial color="#2f6b4f" transparent opacity={.55} side={THREE.DoubleSide}/></mesh>}
    <Html position={[.9,5.8,.9]} center zIndexRange={[8,0]}>
      <button className={`asset-label ${warning?'warning':''} ${hovered?'hovered':''}`} onClick={()=>onSelect(asset.id)}>{asset.id}{warning&&<span>!</span>}</button>
    </Html>
  </group>;
}

/** A slow pulse draws the eye to the asset that needs attention without the page having to shout. */
function WarningRing(){
  const ring=useRef<THREE.Mesh>(null);
  useFrame(state=>{
    if(!ring.current)return;
    const pulse=1+Math.sin(state.clock.elapsedTime*1.8)*.06;
    ring.current.scale.set(pulse,pulse,1);
    (ring.current.material as THREE.MeshBasicMaterial).opacity=.55+Math.sin(state.clock.elapsedTime*1.8)*.22;
  });
  return <mesh ref={ring} rotation={[-Math.PI/2,0,0]} position={[0,.15,0]}><ringGeometry args={[1.25,1.44,44]}/><meshBasicMaterial color="#ce703b" transparent opacity={.8} side={THREE.DoubleSide}/></mesh>;
}

function SolarBlock({asset,onSelect}:{asset:Asset;onSelect:(id:string)=>void}){
  const ref=useRef<THREE.InstancedMesh>(null);
  const {hovered,bind}=useHover();
  useLayoutEffect(()=>{
    if(!ref.current)return;
    const o=new THREE.Object3D();
    let i=0;
    for(let z=0;z<4;z++)for(let x=0;x<5;x++){
      o.position.set(x*.83-1.7,.38+Math.sin(.28)*.5,z*.93-1.4);
      o.rotation.set(-.28,0,0);
      o.updateMatrix();
      ref.current.setMatrixAt(i++,o.matrix);
    }
    ref.current.instanceMatrix.needsUpdate=true;
  },[]);
  const watch=asset.status==='Watch';
  return <group position={[asset.position[0],.1,asset.position[1]]} onClick={e=>{e.stopPropagation();onSelect(asset.id);}} {...bind}>
    <mesh position={[0,0,0]} receiveShadow><boxGeometry args={[4.45,.08,4.4]}/><meshStandardMaterial color="#b3b892" roughness={.95}/></mesh>
    {/* Higher metalness than the rest of the site: glass under a low sun is the one genuinely shiny thing here. */}
    <instancedMesh ref={ref} args={[undefined,undefined,20]} castShadow>
      <boxGeometry args={[.77,.06,.8]}/>
      <meshStandardMaterial color={watch?'#46566a':'#22405a'} roughness={.22} metalness={.55} emissive={hovered?'#5f8fb5':'#000000'} emissiveIntensity={hovered?.35:0}/>
    </instancedMesh>
    {hovered&&<mesh rotation={[-Math.PI/2,0,0]} position={[0,.07,0]}><ringGeometry args={[3.1,3.3,4]}/><meshBasicMaterial color="#2f6b4f" transparent opacity={.5} side={THREE.DoubleSide}/></mesh>}
    <Html position={[0,.6,2.6]} center zIndexRange={[7,0]}>
      <button className={`solar-label ${watch?'watch':''} ${hovered?'hovered':''}`} onClick={()=>onSelect(asset.id)}>{asset.id}</button>
    </Html>
  </group>;
}

function Shrubs(){
  const ref=useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(()=>{
    if(!ref.current)return;
    const o=new THREE.Object3D();
    const tint=new THREE.Color();
    for(let i=0;i<90;i++){
      const x=Math.sin(i*52.7)*15,z=Math.cos(i*39.4)*11;
      const size=.16+(Math.sin(i*24.3)+1)*.14;
      o.position.set(x,.1+size*.6,z);
      o.rotation.set(0,i*1.7,0);
      o.scale.set(size*1.4,size*(.9+Math.sin(i*11.3)*.25),size);
      o.updateMatrix();
      ref.current.setMatrixAt(i,o.matrix);
      // Per-instance colour so ninety identical blobs read as planting rather than pixels.
      ref.current.setColorAt(i,tint.setHSL(.24+Math.sin(i*7.1)*.03,.22+Math.sin(i*3.3)*.07,.34+Math.sin(i*5.9)*.07));
    }
    ref.current.instanceMatrix.needsUpdate=true;
    if(ref.current.instanceColor)ref.current.instanceColor.needsUpdate=true;
  },[]);
  return <instancedMesh ref={ref} args={[undefined,undefined,90]} castShadow receiveShadow>
    <icosahedronGeometry args={[1,1]}/>
    <meshStandardMaterial roughness={1}/>
  </instancedMesh>;
}

function Terrain(){
  // Field parcels in slightly different greens, so the site looks farmed rather than printed on one flat sheet.
  const parcels=useMemo(()=>[
    {pos:[-8.2,-6.6] as const,size:[13.6,11.2] as const,colour:'#b0bb88'},
    {pos:[7.4,-6.6] as const,size:[15.4,11.2] as const,colour:'#bac48f'},
    {pos:[-8.2,5.2] as const,size:[13.6,12.4] as const,colour:'#a8b381'},
    {pos:[7.4,5.2] as const,size:[15.4,12.4] as const,colour:'#b6c08b'},
  ],[]);
  return <group>
    <mesh position={[0,-.52,0]} receiveShadow castShadow><boxGeometry args={[33,1,26]}/><meshStandardMaterial color="#a89a72" roughness={1}/></mesh>
    <mesh position={[0,0,0]} receiveShadow><boxGeometry args={[33,.04,26]}/><meshStandardMaterial color="#b5bf90" roughness={1}/></mesh>
    {parcels.map(p=><mesh key={`${p.pos[0]}:${p.pos[1]}`} position={[p.pos[0],.025,p.pos[1]]} receiveShadow>
      <boxGeometry args={[p.size[0],.03,p.size[1]]}/><meshStandardMaterial color={p.colour} roughness={1}/>
    </mesh>)}
    {[-6,2,6].map(z=><mesh key={z} position={[0,.05,z]} receiveShadow><boxGeometry args={[31,.045,.65]}/><meshStandardMaterial color="#ddd5b2" roughness={.95}/></mesh>)}
    {[-10,-1,10].map(x=><mesh key={x} position={[x,.07,1]} receiveShadow><boxGeometry args={[.55,.04,23]}/><meshStandardMaterial color="#ddd5b2" roughness={.95}/></mesh>)}
    <Shrubs/>
    <group position={[3,.2,4.1]}>
      <mesh position={[0,.45,0]} castShadow receiveShadow><boxGeometry args={[2.2,.9,1.2]}/><meshStandardMaterial color="#e6e6dc" roughness={.75}/></mesh>
      <mesh position={[0,.94,0]} castShadow><boxGeometry args={[2.4,.12,1.4]}/><meshStandardMaterial color="#6f7770" roughness={.6}/></mesh>
      {[-.7,0,.7].map(x=><mesh key={x} position={[x,.5,.61]}><boxGeometry args={[.32,.3,.03]}/><meshStandardMaterial color="#35494b" roughness={.25} metalness={.35}/></mesh>)}
    </group>
  </group>;
}

class SceneBoundary extends Component<{children:React.ReactNode;fallback:React.ReactNode},{failed:boolean}>{
  state={failed:false};
  static getDerivedStateFromError(){return{failed:true};}
  render(){return this.state.failed?this.props.fallback:this.props.children;}
}

export default function FarmScene({assets,onSelect,warning=true}:{assets:Asset[];onSelect:(id:string)=>void;warning?:boolean}){
  // Clears the hand cursor if the pointer leaves the canvas while still over an asset.
  const release=useCallback(()=>{document.body.style.cursor='';},[]);
  return <SceneBoundary fallback={<div className="scene-fallback"><p>3D is unavailable on this device. Select an asset below.</p>{assets.map(a=><button key={a.id} className="button secondary" onClick={()=>onSelect(a.id)}>{a.id}</button>)}</div>}>
    <Canvas shadows dpr={[1,1.5]} gl={{antialias:true,powerPreference:'low-power',alpha:true}} onPointerLeave={release}>
      <OrthographicCamera makeDefault position={[27,23,33]} zoom={17} near={.1} far={200}/>
      {/* Sky above, warm ground bounce below: the cheapest way to get shape into pale surfaces. */}
      <hemisphereLight args={[SKY,GROUND_BOUNCE,1.0]}/>
      <ambientLight intensity={.2}/>
      <directionalLight position={[-12,25,10]} intensity={2.45} color={KEY_LIGHT} castShadow shadow-mapSize={[1024,1024]} shadow-camera-left={-30} shadow-camera-right={30} shadow-camera-top={30} shadow-camera-bottom={-30} shadow-normalBias={.04} shadow-bias={-.0004}/>
      {/* Cool rim from behind, no shadows of its own: separates the towers from the background. */}
      <directionalLight position={[16,9,-18]} intensity={.5} color="#cddcea"/>
      <GroundShadow/>
      <Terrain/>
      {assets.map(a=>a.type==='wind'
        ?<Turbine key={a.id} asset={a} onSelect={onSelect} warning={a.id==='T-03'&&warning}/>
        :<SolarBlock key={a.id} asset={a} onSelect={onSelect}/>)}
      <OrbitControls makeDefault enablePan={false} minZoom={10} maxZoom={28} minPolarAngle={.5} maxPolarAngle={1.15} target={[0,2.2,0]} enableDamping dampingFactor={.08} autoRotate={false}/>
    </Canvas>
  </SceneBoundary>;
}
