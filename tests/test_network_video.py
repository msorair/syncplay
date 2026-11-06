import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

from syncplay import constants
from syncplay.client import SyncplayClient, SyncplayPlaylist, SyncplayUser
from syncplay.players.mpv import MpvPlayer
from syncplay.protocols import SyncClientProtocol


class PlaylistTests(unittest.TestCase):
    oldURL = "https://youtube.com/watch?v=old"
    newURL = "https://youtube.com/watch?v=new"

    def setUp(self):
        self.client = client = object.__new__(SyncplayClient)
        client.ui = Mock()
        client._config = {
            "sharedPlaylistEnabled": True,
            "filenamePrivacyMode": constants.PRIVACY_SENDRAW_MODE,
            "filesizePrivacyMode": constants.PRIVACY_SENDRAW_MODE,
        }
        client.serverFeatures = {}
        client._player = Mock()
        client.userlist = SimpleNamespace(currentUser=SyncplayUser("me", "room"))
        client.delayedLoadPath = None
        client.playlistMayNeedRestoring = False
        client.rewindFile = Mock()
        client.openFile = Mock()
        client.autoplayCheck = Mock()
        client.playlist = SyncplayPlaylist(client)
        client.playlist._playlist = [self.oldURL]
        client.playlist._playlistIndex = 0
        client.playlist.queuedIndexFilename = None
        client._protocol = SyncClientProtocol(client)
        client._protocol.logged = True
        client._protocol.hadFirstPlaylistIndex = True
        client._protocol.sendMessage = Mock()

    def test_opened_stream_selects_new_item_before_server_echo(self):
        client = self.client
        client.updateFile("new", 600, self.newURL)

        self.assertEqual(client.playlist._playlist, [self.oldURL, self.newURL])
        self.assertEqual(client.playlist._playlistIndex, 1)
        settings = [
            message.args[0]["Set"] for message in client._protocol.sendMessage.call_args_list
            if any(key in message.args[0].get("Set", {})
                   for key in ("playlistChange", "playlistIndex"))
        ]
        self.assertIn({"playlistIndex": {"index": 1}}, settings)

        for setting in settings:
            echoed = {key: dict(value, user="me") for key, value in setting.items()}
            client._protocol.handleSet(echoed)

        client.openFile.assert_not_called()
        self.assertEqual(client.playlist._playlistIndex, 1)
        client.updateFile("new", 600, self.newURL)
        self.assertEqual(client.playlist._playlist, [self.oldURL, self.newURL])

    def test_initial_server_playlist_without_user_opens_without_echo(self):
        client = self.client
        client._protocol.hadFirstPlaylistIndex = False
        client._protocol.handleSet({"playlistChange": {"files": [self.newURL], "user": None}})
        client.isURITrusted = Mock(return_value=True)
        client._protocol.handleSet({"playlistIndex": {"index": 0, "user": None}})

        client.openFile.assert_called_once_with(self.newURL, resetPosition=False)
        client._protocol.sendMessage.assert_not_called()

    def test_offline_stream_is_visible_after_reconnect(self):
        client = self.client
        visible = [self.oldURL]

        def showPlaylist(files, *args):
            visible[:] = files

        client.ui.setPlaylist.side_effect = showPlaylist
        client._protocol.logged = False
        client.updateFile("new", 600, self.newURL)
        self.assertEqual(visible, [self.oldURL, self.newURL])

        client._protocol.logged = True
        client.playlistMayNeedRestoring = True
        client._protocol.handleSet({"playlistChange": {"files": [], "user": None}})
        client._protocol.handleSet({"playlistChange": {"files": visible.copy(), "user": "me"}})
        client._protocol.handleSet({"playlistIndex": {"index": 1, "user": "me"}})
        self.assertEqual(visible, client.playlist._playlist)
        self.assertEqual(client.playlist._playlistIndex, 1)


class MpvLoadingTests(unittest.TestCase):
    streamURL = "https://youtube.com/watch?v=new"

    def setUp(self):
        self.player = player = object.__new__(MpvPlayer)
        player._set_defaults()
        player._client = Mock()
        player._client.getGlobalPosition.return_value = 200
        player._client.getGlobalPaused.return_value = False
        player._listener = Mock()
        player.reactor = Mock()
        player.reactor.callFromThread.side_effect = lambda function, *args: function(*args)
        player._paused = False

    def test_deferred_seek_tracks_room_progress_during_loading(self):
        player = self.player
        player.openFile(self.streamURL, resetPosition=True)
        player._listener.sendLine.reset_mock()
        player.setPosition(200)
        player._listener.sendLine.assert_not_called()
        player._handleUnknownLine("<SyncplayUpdateFile>")
        player._client.getGlobalPosition.return_value = 205
        player._onFileUpdate()
        self.assertIn(call(["set_property", "time-pos", "205"]),
                      player._listener.sendLine.call_args_list)


if __name__ == "__main__":
    unittest.main()
