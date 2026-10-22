import {PGlite} from '@electric-sql/pglite';
import {PGLiteSocketServer} from '@electric-sql/pglite-socket';
const db = await PGlite.create();
const server = new PGLiteSocketServer({db,host:'127.0.0.1',port:55432});
await server.start();
console.log('Disposable embedded PostgreSQL ready');
