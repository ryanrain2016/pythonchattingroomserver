
import socketserver, uuid, json, random
import threading
class ThreadUDPServer(socketserver.ThreadingUDPServer):
    def __init__(self,*args,**kwargs):
        super(ThreadUDPServer,self).__init__(*args,**kwargs)
        self.online = {}
        self.rooms={}

    def genid(self):
        return str(uuid.uuid1())

class ServerHandler(socketserver.BaseRequestHandler):
    def setup(self):
        self.room = None

    def dispach(self,data):
        if data and 'action' in data:
            meth = getattr(self,'On'+data['action'],None)
            if meth:
                try:
                    retdata = meth(data)
                    self.OnSyncInfo(data)
                except KeyError:
                    raise
                    retdata = dict(retcode=-1,message='参数错误！')
                except Exception as e:
                    #raise
                    retdata = dict(retcode=-1,message=e.args[0])
            else:
                retdata = dict(retcode=-1,message='参数错误！')
        else:
            retdata = dict(retcode=-1,message='参数错误！')
        try:
            self.request[1].sendto(bytes(json.dumps(retdata),'utf-8'),self.client_address)
        except:
            self.request[1].sendto(bytes(json.dumps(dict(retcode=1)),'utf-8'),self.client_address)

    def handle(self):
        recv_data = None
        data = str(self.request[0].strip(),'utf-8')
        print((self.request,self.client_address))
        try:
            recv_data = json.loads(data)
        except json.decoder.JSONDecodeError:
            print("Invalid data:",data)
        self.dispach(recv_data)

    def finish(self):
        pass

    def isonline(self,data):
        userid = data['userid']
        if userid not in self.server.online:
            raise Exception('用户不在线')
        return userid

    def OnConnection(self,data):    #nickname      ---->userid, roomlist
        nick = data['nickname']
        userid=self.server.genid()
        self.server.online[userid]=dict(currentroom=None, 
            nickname=nick,
            sock=self.request[1],
            addr=self.client_address)
        rooms = self.server.rooms
        rooms = {k:rooms[k]['name'] for k in rooms}
        return dict(retcode=0, userid=userid, roomlist=rooms ,message='连接成功!')

    def OnSyncInfo(self,data):
        action = data['action']
        userid = data.get('userid',None)
        if userid is None:
            return
        online = self.server.online
        if action=='CreateRoom':
            roomname = data['roomname']
            roomid = online[userid]['currentroom']
            data = dict(retcode=2,action='AddRoom',roomid=roomid,roomname=roomname)
            users = online.values()
        elif action=='JoinRoom':
            roomid = data['roomid']
            room = self.server.rooms[roomid]
            users = [online[x] for x in room['member']]
            nickname = online[userid]['nickname']
            data = dict(retcode=2, action='JoinRoom', userid=userid, nickname=nickname)
        elif action=='ExitRoom':
            cur_roomid = online[userid]['currentroom']
            if not cur_roomid:
                return
            cur_room = self.server.rooms[cur_roomid]
            users = [online[x] for x in cur_room['member']]
            nickname = online[userid]['nickname']
            data = dict(retcode=2, action='ExitRoom', userid=userid, nickname=nickname)
        elif action=='Chat':
            return
        elif action=='OnQuit':
            return self.OnSyncInfo(dict(userid=userid,action='ExitRoom'))
        elif action=='DelRoom':
            users = online.values()
            data = dict(retcode=2,action='DelRoom',roomid=data['roomid'],roomname=data['roomname'])
        else:
            return
        data = bytes(json.dumps(data),'utf-8')
        [user['sock'].sendto(data,user['addr']) for user in users]

    def OnCreateRoom(self,data):   #userid,roomname  ------->roomid
        userid = self.isonline(data)
        self.OnExitRoom(data)
        roomname = data['roomname']
        roomid = self.server.genid()
        self.server.rooms[roomid]=dict(name=roomname, member={userid})
        self.server.online[userid]['currentroom']=roomid
        return dict(retcode=0, roomid=roomid, message='房间[%s]创建成功!'%roomname)

    def OnJoinRoom(self,data):          #userid,roomid      --->members
        userid = self.isonline(data)
        roomid = data['roomid']
        if roomid not in self.server.rooms:
            raise Exception('房间不存在')
        self.server.rooms[roomid]['member'].add(userid)
        cur_room = self.server.online[userid]['currentroom']
        if cur_room==roomid:
            raise Exception('你本来就在这个房间！')
        if cur_room:
            self.OnExitRoom(data)
            self.OnSyncInfo(dict(userid=userid,action='ExitRoom'))
        self.server.online[userid]['currentroom']=roomid
        room = self.server.rooms[roomid]
        members = {x:self.server.online[x]['nickname'] for x in room['member']}
        return dict(retcode=0, members=members, message='房间[%s]加入成功!'%room['name'])

    def OnExitRoom(self,data):           #userid         ---->roomlist
        userid = self.isonline(data)
        rooms = self.server.rooms
        rooms = {k:rooms[k]['name'] for k in rooms}
        roomid = self.server.online[userid]['currentroom']
        if roomid:
            roomname = self.server.rooms[roomid]['name']
            self.server.online[userid]['currentroom'] = None
            self.server.rooms[roomid]['member'].discard(userid)
            if not len(self.server.rooms[roomid]['member']):
                del self.server.rooms[roomid]
                self.OnSyncInfo(dict(userid = userid,action='DelRoom',roomid=roomid,roomname=roomname))
            return dict(retcode=0,roomlist=rooms, message='退出房间[%s]成功!'%roomname)
        else:
            return dict(retcode=0,roomlist=rooms, message='')
 
    def OnChat(self,data):                 #userid,message,to(可选)             ->_from,message
        userid = self.isonline(data)
        message = data['message']
        to = data.get('to',None)
        if to and to in self.server.online:
            socks = [self.server.online[to]['sock']]
        else:
            roomid = self.server.online[userid]['currentroom']
            userids = self.server.rooms[roomid]['member']
            users = [self.server.online[x] for x in userids]
        data = bytes(json.dumps(dict(retcode=1, _from=self.server.online[userid]['nickname'], message=message)),'utf-8')
        for user in users:
            sock = user['sock']
            addr = user['addr']
            sock.sendto(data,addr)
        return dict(retcode=3,message='消息发送成功')

    def OnQuit(self, data):            #userid
        userid = self.isonline(data)
        roomid = self.server.online[userid]['currentroom']
        sock = self.server.online[userid]['sock']
        addr = self.server.online[userid]['addr']
        del self.server.online[userid]
        self.server.rooms[roomid]['member'].discard(userid)
        return dict(retcode=0,message='退出成功！')

if __name__=='__main__':
    server = ThreadUDPServer(('0.0.0.0',8000),ServerHandler)
    thd = threading.Thread(target=server.serve_forever)
    thd.setDaemon(True)
    thd.start()
    while True:
        cmd = input('>>>')
        if cmd =='show':
            online = server.online
            online = {userid:dict(nickname=online[userid]['nickname'],currentroom=online[userid]['currentroom'])   for userid in online}
            rooms = {k:dict(name=server.rooms[k]['name'], members=list(server.rooms[k]['member'])) for k in server.rooms}
            print(json.dumps(rooms,indent=4))
            print(json.dumps(online,indent=4))
        elif cmd == 'quit' or cmd =='exit':
            server.shutdown()
            server.server_close()
            break