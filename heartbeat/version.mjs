// Release compatibility floor, not an exact host pin. Prereleases fail closed.
export function atLeast(actual, minimum='2.0.32') {
  const parse=s=>typeof s==='string'&&/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(s)?s.split('.').map(Number):null;
  const a=parse(actual),b=parse(minimum);
  if(!a||!b)return false;
  for(let i=0;i<3;i++){if(a[i]!==b[i])return a[i]>b[i];}
  return true;
}
