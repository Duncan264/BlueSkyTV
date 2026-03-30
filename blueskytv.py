import asyncio
import websockets
import json as js
import re
import mpv
import yt_dlp
import urllib.parse as urlparse
import random


player = mpv.MPV(ytdl=True, input_default_bindings=True, input_vo_keyboard=True, osc=True)
id_epoch = {}


class MyLogger:
    def debug(self, msg):
        # For compatibility with youtube-dl, both debug and info are passed into debug
        # You can distinguish them by the prefix '[debug] '
        if msg.startswith('[debug] '):
            pass
        else:
            self.info(msg)

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)
    
class DownloadHandler:
    def __init__(self, forward_length = 10, backward_length = 2):
        self.background_tasks = set()
        self.forward_length = forward_length #How many videos should be in que ahead
        self.backward_length = backward_length
        self.listening = False #Checking blue sky for new video to be posted
    
    async def update(self, index, length):
        #print ((length - index) < self.forward_length)
        if (length - index) < self.forward_length: #if queue not full of downloaded/downloading videos create a new one
            if not self.listening: #Make sure no other process is already waiting on a link to be posted
                if (len(self.background_tasks) < self.forward_length):
                    task = asyncio.create_task(self.download()) #create a new downloader and add it to a background task
                    self.background_tasks.add(task)
                    task.add_done_callback(self.background_tasks.discard)

                
    async def download(self): #Gets a link form blue sky, wait for it to download, and then add it to the player
        try:
            id = random.randrange(999999)
            self.listening = True 
            link = await get_id()
            self.listening = False
            loop = asyncio.get_running_loop()
            print(await loop.run_in_executor(None, download_video, link))
            player.playlist_append("videos\\"+link+"-"+id_epoch[link]+".webm")
            return link
        except:
            self.listening = False
            print('Error')
                
                

# ℹ️ See "progress_hooks" in help(yt_dlp.YoutubeDL)
def my_hook(d):
    if d['status'] == 'finished':
        id_epoch[d['info_dict']['id']] = str(d['info_dict']['epoch'])
        print('Done downloading, now post-processing ...')

def clip(info_dict, ydl):
    dur = info_dict['duration']
    print (dur)
    start = random.randrange(0, dur-15)
    end = start+15
    print(start)
    print(end)
    return [{'start_time':start, 'end_time':end}]

#ydl_opts = {
#    'logger': MyLogger(),
#    'progress_hooks': [my_hook],
#    'outtmpl': 'videos/%(id)s',
#    'merge_output_format':'webm',
#    'cookiesfrombrowser':('firefox', None, None, None)
#}

ydl_opts = {
    'logger': MyLogger(),
    'progress_hooks': [my_hook],
    'outtmpl': 'videos\%(id)s-%(epoch)s',
    'merge_output_format':'webm',
    'download_ranges': clip,
    'cookiesfrombrowser':('firefox', None, None, None),
    'force_keyframes_at_cuts':False
}


def video_id(value): #Get id from link
    """
    Examples:
    - http://youtu.be/SA2iWivDJiE
    - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    - http://www.youtube.com/embed/SA2iWivDJiE
    - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    """
    query = urlparse.urlparse(value)
    if query.hostname == 'youtu.be':
        return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        if query.path == '/watch':
            p = urlparse.parse_qs(query.query)
            return p['v'][0]
        if query.path[:7] == '/embed/':
            return query.path.split('/')[2]
        if query.path[:3] == '/v/':
            return query.path.split('/')[2]
    # fail?
    return None

async def handler(websocket): #Watch bluesky for youtube link
    done = False
    file = None
    while not done:
        message = await websocket.recv()
        post = js.loads(message)
        try:
            text = (post["commit"]["record"]["text"])
            facets = post["commit"]["record"]["facets"]
            words = text.split(" ")
            #search1 = re.search("youtube.com", text)
            for facet in facets:
                features = facet['features']
                for feature in features:
                    try:
                        search2 = re.search("youtube.com/watch", feature['uri'])
                        if (search2 != None):
                            """                             print(search2)
                            print('position: ')
                            print("---")
                            print(message)
                            print("---")
                            print("https://bsky.app/profile/" + post["did"] + "/post/" + post["commit"]["rkey"])
                            print()
                            print(text)
                            print(feature['uri']) """
                            done = True
                            file = feature['uri']
                            with open("log.txt", "a") as myfile:
                                myfile.write("----\n")
                                myfile.write("https://bsky.app/profile/" + post["did"] + "/post/" + post["commit"]["rkey"])
                                myfile.write("\n\n")
                                myfile.write(message)
                                myfile.write("\n\n")
                                myfile.write(feature['uri'])
                                myfile.write("\n\n")
                    except KeyError:
                        pass
        except KeyError:
            pass
    return file
        
async def get_id():
    print('test')
    url = 'wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post'
    async with websockets.connect(url) as ws:
        print ('start')
        link = await handler(ws)
        print ('finish')
        return video_id(link)
        await asyncio.Future()  # run forever

def download_video(link):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([link])
        

async def player_manager():
    h = DownloadHandler(forward_length = 5, backward_length = 2)
    while True:
        await asyncio.sleep(1)
        await h.update(player.playlist_pos, len(player.playlist))
    return

async def main():
    player.volume = 60
    player.play("./start.webm")
    print(player.playlist)
    await player_manager()



if __name__ == "__main__":
    asyncio.run(main())