import Link from 'next/link';
import {Compass} from 'lucide-react';
export default function NotFound(){return <div className="empty-state"><Compass size={42}/><h1>This route is off the map.</h1><p>Return to the fleet to find an asset, review a warning or plan maintenance.</p><Link className="button primary" href="/">Open fleet overview</Link></div>;}
