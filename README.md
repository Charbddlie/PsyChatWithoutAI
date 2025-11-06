## 预先准备
运行只需要python，开发还需要node

## 运行
不论直接本地运行或打包前端程序都需要先运行
```sh
npm install
```
### 本地开发 
```sh
npm run dev
```
dev和build模式访问的后端地址在src\config.js中设置

### 打包
```sh
npm run build
```
然后可以上传到服务器启动，或者直接在本地启动
启动指令
```sh
cd dist
python -m http.server 8080
```


获取实验数据
```SH
# 下载到运行目录
curl -o noai_record.tsv http://8.153.195.92:8765/user-record

# 在mac的终端运行，下载到桌面
curl -o ~/Desktop/noai_record.tsv http://8.153.195.92:8765/user-record
```
