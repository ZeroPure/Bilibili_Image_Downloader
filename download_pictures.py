import os
import time
import requests
from lxml import etree
import tkinter as tk
from tkinter import messagebox
import threading
import queue
from concurrent.futures import ThreadPoolExecutor,as_completed


class ImageDownloader:
    #请求头
    headers = {
        "Cookie":"",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "referer": "https://www.bilibili.com/read/cv36269093/"
    }
    # 使用相对路径，每使用一次在resource目录下新建一个download文件夹存储图片，避免搞乱
    # 根目录
    base_dir = "resource/"

    #初始化,建议自己更新一下Cookie，referer
    def __init__(self,url,Cookie=None,UserAgent=None,referer=None):
       self.url = url
       if Cookie is not None:
           self.headers["Cookie"] = Cookie

       if UserAgent is not None:
           self.headers["User-Agent"] = UserAgent

       if referer is not None:
           self.headers["referer"] = referer


       self.useFolder = ""  # 用于保存文件夹路径
       self.lock = threading.Lock()#确保线程安全
       self.download_counter = 0#保证进度的顺序性
       self.create_download_folder()

    #创建文件夹
    def create_download_folder(self):
        i = 1
        while True:
            current_folder = os.path.join(self.base_dir, f"download{i}")
            if not os.path.exists(current_folder):
                os.makedirs(current_folder)
                print(f"新建文件夹:{current_folder}")
                self.useFolder = current_folder
                break
            i += 1

    #下载单张图片
    def download_single_image(self,img_url,total_images,flag,status_queue):
        # 这里是判断img的类型是data_src还是src
        if flag == 0:
            cleaned_url = img_url.split('@')[0]
        else:
            cleaned_url = img_url

        # 补充完善url地址
        if cleaned_url.startswith('//'):
            cleaned_url = 'https:' + cleaned_url

        # 通过请求新链接来下载图片
        try:
            img_response = requests.get(cleaned_url, headers=self.headers)
            img_response.raise_for_status()

            #线程锁，保证各个线程之间是有序的
            with self.lock:
                self.download_counter += 1
                img_filename = os.path.join(self.useFolder, f"image_{self.download_counter}.png")
                status_queue.put(f"downloading:{self.download_counter}/{total_images} {img_filename}")


            # 创建文件夹和文件
            with open(img_filename, "wb") as f:
                f.write(img_response.content)


        #请求出错
        except requests.RequestException as e:
            status_queue.put(f"download failed:{cleaned_url},wrong log:{e}")

    #下载图片
    def download_image(self,status_queue):
        # flag = 0 表示是src, flag = 1 表示是data_src
        flag = 0

        response = requests.get(url=self.url, headers=self.headers, timeout=10)
        page = response.content.decode()
        #print(page)

        # xml解析html页面
        html = etree.HTML(page)
        img_srcs = html.xpath('//img[not(ancestor::div[@class="article-comment"])]/@src')

        # 这一段是针对img里的src和data_src的，B站img有两种类型
        if len(img_srcs) == 0:
            img_srcs = html.xpath('//img[not(ancestor::div[@class="article-comment"])]/@data-src')
            flag = 1

        total_images = len(img_srcs)

        #线程池
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self.download_single_image, img_src, total_images, flag, status_queue)
                for index, img_src in enumerate(img_srcs)
            ]


        #及时更新各个线程进度
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                status_queue.put(f"下载失败,原因:{e}")

        status_queue.put(f"下载完成NICE!!!")


#GUI类
class App:
    def __init__(self,master):
        self.master = master
        master.title("Bilibili Images Downloader")

        master.geometry("600x400+100+100")

        #URL输入框
        self.label = tk.Label(master,text="请输入要下载图片的地址(目前仅限于bilibili动态和专栏):")
        self.label.pack()
        self.url_entry = tk.Entry(master,width=50)
        self.url_entry.pack()

        #cookie输入框
        self.cookie_label = tk.Label(master,text="cookie输入(可选):")
        self.cookie_label.pack()
        self.cookie_entry = tk.Entry(master,width=50)
        self.cookie_entry.pack()

        #User-Agent输入框
        self.user_agent_label = tk.Label(master,text="User-Agent输入(可选):")
        self.user_agent_label.pack()
        self.user_agent_entry = tk.Entry(master,width=50)
        self.user_agent_entry.pack()

        #referer输入框
        self.referer_label = tk.Label(master,text="referer输入(可选):")
        self.referer_label.pack()
        self.referer_entry = tk.Entry(master,width=50)
        self.referer_entry.pack()

        #下载按钮
        self.download_button = tk.Button(master,text="下载图片",command=self.download)
        self.download_button.pack()

        self.status_label = tk.Label(master, text="")
        self.status_label.pack()

        #记录状态的队列
        self.status_queue = queue.Queue()
        self.update_status()

    #点击下载图片按钮后会调用此方法
    def download(self):
        url = self.url_entry.get()
        cookie = self.cookie_entry.get() or None
        user_agent = self.user_agent_entry.get() or None
        referer = self.referer_entry.get() or None

        if not url:
            messagebox.showerror("错误","请重新输入有效的链接地址")
            return

        # 建立一个ImageDownloader对象
        self.status_label.config(text="downloading...")
        downloader = ImageDownloader(url=url,Cookie=cookie,UserAgent=user_agent,referer=referer)

        # 将下载操作放入新线程(子线程去启用线程池)
        threading.Thread(target=self.download_images, args=(downloader,)).start()


    def download_images(self,downloader):
        downloader.download_image(self.status_queue)


    #更新GUI(主线程)
    def update_status(self):
        try:
            while True:
                message = self.status_queue.get_nowait()
                self.status_label.config(text=message)
        except queue.Empty:
            pass
        self.master.after(100,self.update_status)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()







