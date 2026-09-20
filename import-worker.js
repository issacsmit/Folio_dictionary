import {importPack} from './lib/import.js';
self.onmessage = async ({data}) => {
  try {const pack = await importPack(data.file, value => self.postMessage({type: 'progress', ...value})); self.postMessage({type: 'complete', pack});}
  catch (error) {self.postMessage({type: 'error', message: error.message || '导入失败，请检查词典包。'});}
};
