const version = _em.ccall("csmGetVersion", "number", [], []);
console.log('Version:', version);