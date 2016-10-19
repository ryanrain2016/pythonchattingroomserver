import wx, socket, threading,json,time

class ChatFrame(wx.Frame):
    def __init__(self):
        default_size = (600,600)
        wx.Frame.__init__(self,None,-1, '聊天室', size=default_size)
        self.SetMaxSize(default_size)   #与下一行的作用是固定大小
        self.SetMinSize(default_size)
        self.panel = wx.Panel(self,-1)
        self.panel.SetFocus()
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.server_addr = ('123.207.170.247',8000)
        #self.server_addr = ('127.0.0.1',8000)
        dlg = wx.TextEntryDialog(None,'请设置昵称：','昵称','')
        if dlg.ShowModal() == wx.ID_OK:
            nickname = dlg.GetValue()
        else:
            nickname = 'user%s'%(int(time.time()))
        dlg.Destroy()
        self.nickname = nickname
        self.cur_members = []
        self.userid = None
        self.initUI()
        self.updateUI()
        self.Show()

    def Destroy(self):
        data = dict(action='Quit',userid=self.userid)
        self.send(data)
        return super().Destroy()

    def initUI(self):
        self.roomlistctrl = wx.ListBox(self.panel,-1,choices=['未连接'],size = (100,500))
        self.createroombutton = wx.Button(self.panel,0,'创建房间',size=(100,100))
        self.sessionareactrl = wx.TextCtrl(self.panel,-1,style=wx.TE_MULTILINE | wx.TE_READONLY,size=(400,400))
        self.memberctrl = wx.ListBox(self.panel,-1,choices=[],size = (100,400))
        self.inputctrl = wx.TextCtrl(self.panel,-1,style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER,size=(400,200))
        self.sendbutton = wx.Button(self.panel,1,'发送',size=(100,200))
        self.inputctrl.SetFocus()
        self.sessionareactrl.SetEditable(False)
        self.sessionareactrl.SetCanFocus(False)
        self.roomlistctrl.Bind(wx.EVT_LISTBOX_DCLICK, self.OnJoinRoom)
        self.createroombutton.Bind(wx.EVT_BUTTON, self.OnCreateRoom)
        self.sendbutton.Bind(wx.EVT_BUTTON, self.OnSend)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnSend, self.inputctrl)
        sizer1 = wx.BoxSizer(orient = wx.VERTICAL)
        sizer1.Add(self.roomlistctrl)
        sizer1.Add(self.createroombutton)
        sizer2 = wx.BoxSizer()
        sizer2.Add(self.sessionareactrl)
        sizer2.Add(self.memberctrl)
        sizer3 = wx.BoxSizer()
        sizer3.Add(self.inputctrl)
        sizer3.Add(self.sendbutton)
        sizer4 = wx.BoxSizer(orient = wx.VERTICAL)
        sizer4.Add(sizer2)
        sizer4.Add(sizer3)
        sizer = wx.BoxSizer()
        sizer.Add(sizer1)
        sizer.Add(sizer4)
        self.panel.SetSizer(sizer)

    def updateuithd(self):
        self.connect()
        while True:
            data=self.sock.recvfrom(102400)
            data = str(data[0], 'utf-8')
            data = json.loads(data)
            print(data)
            retcode = data['retcode']
            if retcode==0:
                wx.CallAfter(self.sessionareactrl.AppendText,data['message']+'\n')
                if 'userid' in data:
                    self.userid = data['userid']
                if 'roomlist' in data:
                    roomdict = data['roomlist']
                    self.roomlist = [(k,roomdict[k]) for k in roomdict]
                    roomchoice = [x[1] for x in self.roomlist]
                    wx.CallAfter(self.roomlistctrl.Set,roomchoice)
                if 'roomid' in data:
                    self.roomid = data['roomid']
                if 'members' in data:
                    self.cur_members =[(k, data['members'][k]) for k in data['members']]
                    memberschoice = [x[1] for x in self.cur_members]
                    wx.CallAfter(self.memberctrl.Set,memberschoice)
            elif retcode==1:
                msg = '[%(_from)s] : %(message)s\n'%data
                wx.CallAfter(self.sessionareactrl.AppendText,msg)
            elif retcode==2:
                action = data['action']
                if action =='AddRoom':
                    if (data['roomid'],data['roomname']) in self.roomlist:
                        continue
                    self.roomlist.insert(0,(data['roomid'],data['roomname']))
                    wx.CallAfter(self.roomlistctrl.InsertItems,[data['roomname']], 0)
                elif action == 'JoinRoom':
                    if (data['userid'],data['nickname']) in self.cur_members:
                        continue
                    self.cur_members.insert(0,(data['userid'],data['nickname']))
                    wx.CallAfter(self.memberctrl.InsertItems,[data['nickname']], 0)
                    wx.CallAfter(self.sessionareactrl.AppendText,'[系统消息] : [%(nickname)s]进入房间了！\n'%data)
                elif action == 'ExitRoom':
                    userid = data['userid']
                    nickname = data['nickname']
                    if (userid,nickname) not in self.cur_members:
                        continue
                    index = self.cur_members.index((userid,nickname))
                    self.cur_members.pop(index)
                    wx.CallAfter(self.memberctrl.Delete, index)
                elif action == 'DelRoom':
                    roomid = data['roomid']
                    roomname = data['roomname']
                    if (roomid,roomname) not in self.roomlist:
                        continue
                    index = self.roomlist.index((roomid,roomname))
                    self.roomlist.pop(index)
                    wx.CallAfter(self.roomlistctrl.Delete,index)
                    wx.CallAfter(self.sessionareactrl.AppendText, '[系统消息] : 房间[%s]被系统删除了！\n'%roomname)
            elif retcode==-1:
                print(data['message'])

    def updateUI(self):
        thd = threading.Thread(target= self.updateuithd)
        thd.setDaemon(True)
        thd.start()

    def send(self,data):
        data = bytes(json.dumps(data),'utf-8')
        self.sock.sendto(data,self.server_addr)

    def connect(self):
        data = dict(action='Connection',nickname=self.nickname)
        self.send(data)

    def OnJoinRoom(self,evt):
        index = evt.Selection
        roomid = self.roomlist[index][0]
        data = dict(action='JoinRoom',userid = self.userid,roomid=roomid)
        self.send(data)

    def OnCreateRoom(self,evt):
        dlg = wx.TextEntryDialog(None,'房间名:','房间名','')
        if dlg.ShowModal() == wx.ID_OK:
            roomname = dlg.GetValue()
        else:
            dlg.Destroy()
            return
        dlg.Destroy()
        data = dict(action='CreateRoom',userid = self.userid,roomname=roomname)
        self.send(data)

    def OnSend(self,evt):
        text = self.inputctrl.GetValue().strip()
        data = dict(action='Chat', userid = self.userid,message=text)
        self.send(data)
        self.inputctrl.SetValue('')

if __name__=='__main__':
    app = wx.App()
    frame = ChatFrame()
    app.MainLoop()