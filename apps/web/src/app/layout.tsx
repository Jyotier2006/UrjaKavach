import type {Metadata,Viewport} from 'next';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/manrope/600.css';
import '@fontsource/manrope/700.css';
import '@fontsource/manrope/800.css';
import './globals.css';
import {Providers} from '@/components/providers';
export const metadata:Metadata={title:{default:'UrjaKavach · Renewable asset intelligence',template:'%s · UrjaKavach'},description:'Detect, investigate and act on renewable asset deviations. An evidence-first operations workspace for solar and wind maintenance.',manifest:'/manifest.webmanifest',icons:{icon:'/icon.svg',apple:'/icons/icon-192.png'},appleWebApp:{capable:true,statusBarStyle:'default',title:'UrjaKavach'}};
export const viewport:Viewport={width:'device-width',initialScale:1,themeColor:'#1e5440'};
// Extensions such as Grammarly add their own attributes to <html> and <body> before React hydrates, which
// React reports as a mismatch it cannot patch. Suppressing here covers attributes on these two elements only;
// a genuine mismatch anywhere inside the app is still reported.
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" suppressHydrationWarning><body suppressHydrationWarning><Providers>{children}</Providers></body></html>;}
