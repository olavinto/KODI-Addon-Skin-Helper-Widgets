#!/usr/bin/python
# -*- coding: utf-8 -*-

import urlparse
from utils import log_msg, ADDON_ID, create_main_entry
from simplecache import SimpleCache
import xbmcplugin
import xbmc
import xbmcaddon
import xbmcgui
import sys
from artutils import ArtUtils, process_method_on_list
import time

ADDON_HANDLE = int(sys.argv[1])


class Main(object):
    '''Main entry path for our widget listing. Process the arguments and load correct class and module'''

    def __init__(self):
        ''' Initialization '''

        self.artutils = ArtUtils()
        self.cache = SimpleCache()
        self.addon = xbmcaddon.Addon(ADDON_ID)
        self.win = xbmcgui.Window(10000)
        self.options = self.get_options()

        # skip if shutdown requested
        if self.win.getProperty("SkinHelperShutdownRequested"):
            log_msg("Not forfilling request: Kodi is exiting!", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)
            return

        if not "mediatype" in self.options or not "action" in self.options:
            # we need both mediatype and action, so show the main listing
            self.mainlisting()
        else:
            # we have a mediatype and action so display the widget listing
            self.show_widget_listing()

        self.close()

    def close(self):
        '''Cleanup Kodi Cpython instances'''
        self.artutils.close()
        self.cache.close()
        del self.addon
        del self.win
        log_msg("MainModule exited")

    def get_options(self):
        '''get the options provided to the plugin path'''

        options = dict(urlparse.parse_qsl(sys.argv[2].replace('?', '').lower().decode("utf-8")))

        if not "mediatype" in options and "action" in options:
            # get the mediatype and action from the path (for backwards compatability with old style paths)
            for item in [
                ("movies", "movies"),
                ("shows", "tvshows"),
                ("episode", "episodes"),
                ("musicvideos", "musicvideos"),
                ("pvr", "pvr"),
                ("albums", "albums"),
                ("songs", "songs"),
                ("media", "media"),
                    ("favourites", "favourites")]:
                if item[0] in options["action"]:
                    options["mediatype"] = item[1]
                    options["action"] = options["action"].replace(item[1], "").replace(item[0], "")
                    break

        # prefer refresh param for the mediatype
        if "mediatype" in options:
            alt_refresh = self.win.getProperty("widgetreload-%s" % options["mediatype"])
            if options["mediatype"] == "favourites" or "favourite" in options["action"]:
                options["skipcache"] = "true"
            elif alt_refresh:
                options["refresh"] = alt_refresh

        # set the widget settings as options
        options["hide_watched"] = self.addon.getSetting("hide_watched") == "true"
        options["next_inprogress_only"] = self.addon.getSetting("nextup_inprogressonly") == "true"
        options["episodes_enable_specials"] = self.addon.getSetting("episodes_enable_specials") == "true"
        options["group_episodes"] = self.addon.getSetting("episodes_grouping") == "true"
        if "limit" in options:
            options["limit"] = int(options["limit"])
        else:
            options["limit"] = int(self.addon.getSetting("default_limit"))
        return options

    def show_widget_listing(self):
        '''display the listing for the provided action and mediatype'''
        media_type = self.options["mediatype"]
        action = self.options["action"]
        refresh = self.options.get("refresh", "")
        # set widget content type
        xbmcplugin.setContent(ADDON_HANDLE, media_type)

        # try to get from cache first...
        # we use a checksum based on the options to make sure the cache is ignored when needed
        all_items = []
        cache_str = "SkinHelper.Widgets.%s.%s" % (media_type, action)
        if not refresh:
            cache_checksum = None
        else:
            cache_checksum = ".".join([repr(value) for value in self.options.itervalues()])
        cache = self.cache.get(cache_str, checksum=cache_checksum)
        if cache and not self.options.get("skipcache") == "true":
            log_msg("MEDIATYPE: %s - ACTION: %s -- got items from cache - CHECKSUM: %s"
                    % (media_type, action, cache_checksum))
            all_items = cache

        # Call the correct method to get the content from json when no cache
        if not all_items:
            log_msg("MEDIATYPE: %s - ACTION: %s -- no cache, quering kodi api to get items - CHECKSUM: %s"
                    % (media_type, action, cache_checksum))

            # dynamically import and load the correct module, class and function
            media_module = __import__(media_type)
            media_class = getattr(media_module, media_type.capitalize())(self.addon, self.artutils, self.options)
            all_items = getattr(media_class, action)()

            # randomize output if requested by skinner or user
            if self.options.get("randomize", "") == "true":
                all_items = sorted(all_items, key=lambda k: random.random())

            # prepare listitems and store in cache
            all_items = process_method_on_list(self.artutils.kodidb.prepare_listitem, all_items)
            self.cache.set(cache_str, all_items, checksum=cache_checksum)

        # fill that listing...
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
        all_items = process_method_on_list(self.artutils.kodidb.create_listitem, all_items)
        xbmcplugin.addDirectoryItems(ADDON_HANDLE, all_items, len(all_items))

        # end directory listing
        xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)

    def mainlisting(self):
        '''main listing'''
        all_items = []

        # movie node
        if xbmc.getCondVisibility("Library.HasContent(movies)"):
            all_items.append((xbmc.getLocalizedString(342), "movieslisting", "DefaultMovies.png"))

        # tvshows and episodes nodes
        if xbmc.getCondVisibility("Library.HasContent(tvshows)"):
            all_items.append((xbmc.getLocalizedString(20343), "tvshowslisting", "DefaultTvShows.png"))
            all_items.append((xbmc.getLocalizedString(20360), "episodeslisting", "DefaultTvShows.png"))

        # pvr node
        if xbmc.getCondVisibility("PVR.HasTvChannels"):
            all_items.append((self.addon.getLocalizedString(32054), "pvrlisting", "DefaultAddonPVRClient.png"))

        # music nodes
        if xbmc.getCondVisibility("Library.HasContent(music)"):
            all_items.append((xbmc.getLocalizedString(132), "albumslisting", "DefaultAddonAlbumInfo.png"))
            all_items.append((xbmc.getLocalizedString(134), "songslisting", "DefaultAddonMusic.png"))

        # musicvideo node
        if xbmc.getCondVisibility("Library.HasContent(musicvideos)"):
            all_items.append((xbmc.getLocalizedString(20389), "musicvideoslisting", "DefaultAddonAlbumInfo.png"))

        # media node
        if xbmc.getCondVisibility(
                "Library.HasContent(movies) | Library.HasContent(tvshows) | Library.HasContent(music)"):
            all_items.append((self.addon.getLocalizedString(32057), "medialisting", "DefaultAddonAlbumInfo.png"))

        # favourites node
        all_items.append((xbmc.getLocalizedString(10134), "favouriteslisting", "DefaultAddonAlbumInfo.png"))

        # process the listitems and display listing
        all_items = process_method_on_list(create_main_entry, all_items)
        all_items = process_method_on_list(self.artutils.kodidb.prepare_listitem, all_items)
        all_items = process_method_on_list(self.artutils.kodidb.create_listitem, all_items)
        xbmcplugin.addDirectoryItems(ADDON_HANDLE, all_items, len(all_items))
        xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)