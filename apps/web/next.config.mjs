const securityHeaders = [
  {key:'Cache-Control',value:'no-store'},
  {key:'X-Content-Type-Options',value:'nosniff'},
  {key:'Referrer-Policy',value:'no-referrer'},
  {key:'X-Frame-Options',value:'DENY'},
  {key:'Permissions-Policy',value:'camera=(), microphone=(), geolocation=()'},
  {key:'Content-Security-Policy',value:"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"}
];
export default {poweredByHeader:false, async headers(){return [{source:'/:path*',headers:securityHeaders}];}};
