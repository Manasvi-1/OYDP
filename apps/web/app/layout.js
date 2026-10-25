import './style.css';
import {connection} from 'next/server';
export const metadata = {title:'OYDP | Private property workspace', description:'Private property candidates and attributed claims'};
export default async function Layout({children}) { await connection(); return <html lang="en"><body>{children}</body></html>; }
