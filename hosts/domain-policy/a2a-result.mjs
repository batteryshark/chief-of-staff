// Only repair the existing transport's optional, own undefined parentID field.
// No JSON round-trip: unrelated invalid values must remain visible to validation.
function replacingValue(object, key, value) {
  const descriptors=Object.getOwnPropertyDescriptors(object), previous=descriptors[key];
  descriptors[key]={value,enumerable:previous?.enumerable ?? true,
    configurable:previous?.configurable ?? true,writable:previous?.writable ?? false};
  return Object.create(Object.getPrototypeOf(object),descriptors);
}

export function adaptA2aResult(result) {
  const metadata=result?.metadata,a2a=metadata?.a2a;
  if (!a2a || typeof a2a!=='object' || !Object.hasOwn(a2a,'parentID') || a2a.parentID!==undefined) return result;
  const descriptors=Object.getOwnPropertyDescriptors(a2a);
  delete descriptors.parentID;
  const adapted=Object.create(Object.getPrototypeOf(a2a),descriptors);
  return replacingValue(result,'metadata',replacingValue(metadata,'a2a',adapted));
}
