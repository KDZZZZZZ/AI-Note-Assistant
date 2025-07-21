<template> 
   <div class="wrapper"> 
     <!-- 1. 左栏：实时文本 --> 
     <aside class="left"> 
        <pre class="chat-response">{{ chatResponse || 'Kimi 的回复将显示在这里…' }}</pre> 
     </aside> 
 
     <!-- 2. 中栏：整份 PDF --> 
     <main class="center" ref="centerEl" @dragover.prevent @drop.prevent="handleFileDrop"> 
             <div v-if="!pdfLoaded" class="drop-zone">
        <p>将 PDF 文件拖放到此处，或</p>
        <button @click="openFileDialog" class="upload-button">选择文件</button>
        <input type="file" ref="fileInput" @change="handleFileSelect" accept=".pdf" hidden>
      </div>
      <div v-else>
        <canvas 
          v-for="page in pdfPages" 
          :key="page.pageNum" 
          class="page" 
          :ref="el => (page.el = el)" 
        /> 
      </div>
     </main> 
 
     <!-- 3. 右栏：Markdown --> 
     <aside class="right"> 
       <article class="markdown-body" v-html="mdHtml"></article> 
     </aside> 
    <div class="float-input-wrapper">
      <textarea class="float-input" v-model="inputText" placeholder="在这里输入文字…" @keydown.enter.prevent="sendMessage"></textarea>
      <button @click="sendMessage" class="send-button">发送</button>
    </div>
    <div class="right-controls">
      <button @click="importMd">导入MD</button>
      <button @click="exportMd">导出MD</button>
      <button @click="clearMd">清空MD</button>
      <input type="file" ref="mdInput" @change="handleMdSelect" accept=".md" hidden>
    </div>
   </div> 
 </template> 
 
 <script setup> 
 import { ref, onMounted, nextTick } from 'vue'
 import axios from 'axios' 
 import { marked } from 'marked' 
 import * as pdfjsLib from 'pdfjs-dist'

 /* ---------- 1. pdf.js 版本对齐 ---------- */ 
 pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'
 
 /* ---------- 2. 响应式数据 ---------- */ 
 const inputText  = ref('') 
 const pdfPages   = ref([])   // { pageNum, el }
 const pdfLoaded  = ref(false) 
 const mdHtml     = ref('')
 const chatResponse = ref('') 
 const centerEl = ref(null)
 
 /* ---------- 3. 加载整份 PDF ---------- */
 async function renderPdf(arrayBuffer) {
   try {
     // 验证arrayBuffer
     if (!arrayBuffer || arrayBuffer.byteLength === 0) {
       throw new Error('PDF文件为空或无效');
     }
     
     const pdfLoadingTask = pdfjsLib.getDocument({
       data: arrayBuffer,
       verbosity: 0 // 减少控制台输出
     });
     const pdf = await pdfLoadingTask.promise;
   const containerWidth = centerEl.value.clientWidth;

   pdfPages.value = Array.from({ length: pdf.numPages }, (_, i) => ({
     pageNum: i + 1,
     el: null,
   }));

   await nextTick();

   for (const pageObj of pdfPages.value) {
     if (!pageObj.el) continue;
     const page = await pdf.getPage(pageObj.pageNum);
     const viewport = page.getViewport({ scale: 1 });
     const scale = (containerWidth - 20) / viewport.width; // 减去 padding
     const scaledViewport = page.getViewport({ scale });

     pageObj.el.height = scaledViewport.height;
     pageObj.el.width = scaledViewport.width;

     const renderContext = {
       canvasContext: pageObj.el.getContext('2d'),
       viewport: scaledViewport,
     };
     await page.render(renderContext).promise;
   }
   } catch (error) {
     console.error('PDF渲染失败:', error);
     pdfLoaded.value = false;
     throw new Error(`PDF渲染失败: ${error.message}`);
   }
 }

 const fileInput = ref(null);

 function openFileDialog() {
   fileInput.value.click();
 }

 async function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file && file.type === 'application/pdf') {
    await processFile(file);
  }
}

 async function handleFileDrop(event) {
   const file = event.dataTransfer.files[0]
   if (file && file.type === 'application/pdf') {
     await processFile(file);
   } else {
     alert('请拖放一个 PDF 文件。')
   }
 } 

 async function processFile(file) {
  try {
    // 验证文件大小和类型
    if (file.size > 50 * 1024 * 1024) { // 50MB限制
      throw new Error('PDF文件过大，请选择小于50MB的文件');
    }
    
    if (!file.type.includes('pdf')) {
      throw new Error('请选择有效的PDF文件');
    }

    // 1. 上传并保存到固定路径
    const form = new FormData();
    form.append("file", file);

    const saveRes = await axios.post("/api/save_file", form, {
      headers: { "Content-Type": "multipart/form-data" }
    });

    // 2. 用固定路径触发后端处理
    await axios.post("/api/upload_files");

    // 3. 获取PDF文件并验证
    const response = await axios.get('/demo.pdf', {
      responseType: "arraybuffer"
    });
    
    const arrayBuffer = response.data;
    
    // 验证PDF文件头
    const uint8Array = new Uint8Array(arrayBuffer.slice(0, 4));
    const header = String.fromCharCode(...uint8Array);
    if (header !== '%PDF') {
      throw new Error('文件不是有效的PDF格式');
    }

    // 切换状态，让 canvas 渲染出来
    pdfLoaded.value = true;
    // 等待 DOM 更新
    await nextTick();
    // 渲染 PDF
    await renderPdf(arrayBuffer);

  } catch (error) {
    console.error('文件处理失败:', error);
    let errorMessage = '文件处理失败';
    
    if (error.message.includes('Invalid PDF')) {
      errorMessage = 'PDF文件结构无效，请检查文件是否损坏';
    } else if (error.message.includes('网络')) {
      errorMessage = '网络连接失败，请检查网络连接';
    } else if (error.message) {
      errorMessage = error.message;
    }
    
    alert(errorMessage);
    pdfLoaded.value = false; // 渲染失败，重置状态
  }
} 
 
 /* ---------- 4. 加载 Markdown ---------- */ 
 async function loadMarkdown() {
  try {
    const response = await axios.get('/note.md', {
      responseType: 'text',
      // 避免浏览器缓存
      headers: {
        'Cache-Control': 'no-cache',
      },
    });
    mdHtml.value = marked.parse(response.data);
  } catch (error) {
    console.error('加载Markdown文件失败:', error);
    mdHtml.value = marked.parse('# 加载失败\n无法加载Markdown文件，请检查文件路径。');
  }
}

onMounted(() => {
  // 初始加载
  loadMarkdown();

  // 添加页面关闭前的清理操作
  window.addEventListener('beforeunload', () => {
    // 使用 navigator.sendBeacon 发送一个POST请求
    // 这是一个可靠的方式，可以在页面卸载时发送数据
    navigator.sendBeacon('/api/cleanup', new Blob());
  });
});
 
 const mdInput = ref(null);

function importMd() {
  if (window.confirm('这将覆盖当前的 Markdown 文件，确定要导入吗？')) {
    mdInput.value.click();
  }
}

async function handleMdSelect(event) {
  const file = event.target.files[0];
  if (file) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      await axios.post('/api/import_md', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      loadMarkdown(); // 手动刷新
    } catch (error) {
      console.error('导入Markdown文件失败:', error);
      alert('导入失败，请检查文件或网络。');
    }
  }
}

async function exportMd() {
  try {
    const response = await axios.get('/file.md', { responseType: 'text' });
    const blob = new Blob([response.data], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'exported_note.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('导出Markdown文件失败:', error);
    alert('导出失败，请检查网络。');
  }
}

async function clearMd() {
  if (confirm('确定要清空所有Markdown内容吗？此操作不可恢复。')) {
    try {
      await axios.post('/api/clear_md');
      loadMarkdown(); // 手动刷新
    } catch (error) {
      console.error('清空Markdown失败:', error);
      alert('清空失败，请检查网络。');
    }
  }
}

/* ---------- 5. 发送消息到后端 ---------- */
async function sendMessage() {
  if (!inputText.value.trim()) return;

  try {
    const rawText = inputText.value.trim(); // 获取原始字符串

    // 发送纯文本的POST请求
    const res = await axios.post('/api/chat', rawText, {
      headers: {
        'Content-Type': 'text/plain' // 明确请求头为纯文本
      }
    });

    if (res.data && res.data.status === 'updated') {
      chatResponse.value = res.data.reply;
      loadMarkdown(); // 手动刷新
    }

    chatResponse.value = res.data; // 直接使用字符串响应
    inputText.value = ''; // 清空输入框

  } catch (error) {
    console.error('通信错误:', error);

    // 错误处理
    if (error.response) {
      // 可以解析后端返回的错误信息，但注意响应类型可能是文本或JSON
      let errorMessage;
      if (typeof error.response.data === 'string') {
        errorMessage = error.response.data;
      } else {
        try {
          // 如果错误响应是JSON（有些后端可能会返回JSON错误）
          errorMessage = error.response.data.detail || JSON.stringify(error.response.data);
        } catch {
          errorMessage = `后端错误：${error.response.status} ${error.response.statusText}`;
        }
      }
      chatResponse.value = errorMessage;
    } else if (error.request) {
      chatResponse.value = '网络错误：请求已发送但未收到响应';
    } else {
      chatResponse.value = '客户端错误：' + error.message;
    }
  }
}
 </script> 
 
 <style scoped> 
 /* ---------- 5. 全局重置 ---------- */ 
 * { 
   margin: 0; 
   padding: 0; 
   box-sizing: border-box; 
 } 
 html, 
 body { 
   height: 100%; 
 } 
 .wrapper { 
   display: flex; 
   height: 100vh; 
 } 
 
 /* ---------- 6. 三栏比例 & 滚动 ---------- */ 
 .left, 
 .center, 
 .right { 
   flex-shrink: 0; 
   overflow-y: auto; 
   /* 隐藏滚动条 WebKit / Firefox */ 
   scrollbar-width: none;      /* Firefox */ 
 } 
 .left::-webkit-scrollbar, 
 .center::-webkit-scrollbar, 
 .right::-webkit-scrollbar { 
   display: none;              /* Chrome / Edge / Safari */ 
 } 
 
 .left  { width: 30%; background: #2c3e50; color: #ecf0f1; padding: 20px; }
 .center { width: 40%; background: #ecf0f1; padding: 10px; }
 .right  { width: 30%; background: #ffffff; padding: 20px; position: relative; }

.right-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 10px;
}

.right-controls button {
  padding: 5px 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  background-color: #f0f0f0;
  cursor: pointer;
}
 
 /* 确保markdown样式正确应用 */
 .right :deep(.markdown-body) {
   background-color: transparent !important;
   color: #24292f !important;
   font-size: 14px;
   font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji" !important;
 }

.drop-zone {
  border: 2px dashed #ccc;
  border-radius: 10px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.upload-button {
  margin-top: 15px;
  padding: 10px 20px;
  border: none;
  background-color: #3498db;
  color: white;
  border-radius: 5px;
  cursor: pointer;
}

.page {
  display: block;
  width: 100%;
  margin-bottom: 10px;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.2);
  background: #fff;
}

.float-input-wrapper {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  display: flex;
}

.float-input {
  flex-grow: 1;
  padding: 15px;
  border-radius: 8px 0 0 8px;
  border: 1px solid #ccc;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  font-size: 16px;
  resize: none;
  z-index: 1000;
}

.send-button {
  padding: 15px 20px;
  border: 1px solid #ccc;
  border-left: none;
  background-color: #3498db;
  color: white;
  border-radius: 0 8px 8px 0;
  cursor: pointer;
  z-index: 1000;
}

.chat-response {
  white-space: pre-wrap; /* or pre-line */
  word-wrap: break-word;
  height: calc(100vh - 120px); /* Adjust based on your layout */
  overflow-y: auto;
}
 </style>