# How to setup PytubePlayer on Home Assistant

Video: https://www.youtube.com/watch?v=LMxd6fsEv9c

1. Add-ons installation:
    1. (*Optional*) **Advanced SSH & Web Terminal:** 
        1. On HA > Settings > Add-ons
        2. Search for “*Advanced SSH & Web Terminal*”, then select and click the [Install] button to install it
        3. After installing it, go t**o** the Configuration and update your username and password in the SSH script. For example, like this:
            
            ```jsx
            username: xxxx // <-- Input your HA's username
            password: yyyy // <-- Input your HA's password
            authorized_keys: []
            sftp: false
            compatibility_mode: false
            allow_agent_forwarding: false
            allow_remote_port_forwarding: false
            allow_tcp_forwarding: false
            ```
            
    2. **Studio Code Server**
        1. On HA > Settings > Add-ons
        2. Search for “*Studio Code Server*”, then select and click [Install] button to install it
2. HACS installation:
    1. **HACS**: You need to install `HACS` to install `Pyscript`
        1. Please follow this [document](https://www.hacs.xyz/docs/use/configuration/basic/) to install HACS
    2. **Pyscript:**
        1. On the HACS, search for *“Pyscript” t*hen select it and click on [Download] button to install it
        2. Open Studio Code Server → select `configuration.yaml` file and add the code here:
            
            ```jsx
            # pyscript
            pyscript:
              allow_all_imports: true
              hass_is_global: true
            
            # pyscript logger
            logger:
              default: info
              logs:
                custom_components.pyscript: info
            ```
            
    3. **Mushroom**
        1. On the HACS, search *“Mushroom” t*hen select it and click on [Download] button to install it
    4. Restart you HA: 
        1. Finally, restart you HA (you can goto **Developer tools** then click [Restart] > [Restart Home Assistant] button to restart it)
3. Manually install the **PytubePlayerServer** and **PytubePlayer**:
    1. After restart your Home Assistant, open **Studio Code Server** 
    2. Make sure, you can see the `pyscript` folder where we put our code here
        1. Copy the code in my project by following the structure here:
        
        ```jsx
        pyscript/
        ├── modules/
        │   ├── file_manager.py
        │   ├── utils.py
        ├── servers/
        │   ├── pytube/
        │       ├── pytube_server.py
        │       ├── requirements.txt
        ├── pytube.py
        ├── servers_startup.py
        ├── requirements.txt
        ```
        
4. Manually update the server’s url for **PytubePlayer:**
    1. On **Studio Code Server**, **g**oto `pyscript` folder→ `pytube.py`
    2. *Optional*: Find the code below and update your BASE URL which is the same with you HA’s IP Address.
        1. For example: My HA’s IP Address is `10.25.113.181` → so, the URL should be: `http://10.25.113.181:114`
    
    ```jsx
    # PUT YOUR CHANGES HERE
    __PYTUBE_BASE_URL = 'http://10.25.113.181:114'    # Base URL for your PyTube API server
    __PYTUBE_CACHE_DAY = 30                           # Cache duration in days (30 days = 1 month). Songs won't be played until cache expires or playlist completes
    __PYTUBE_TIME_OUT = 60                            # API request timeout in seconds
    ```
    
5. Last step:
    1. Some scripts: Create the script to make the automations
        1. Play script:
            1. `entity_id`: Your media player id
            2. `playlist_url`: Your playlist URL — it should be public/unlisted
            3. `is_shuffle`: Shuffle option, `true` → On
            4. `play_time_check`: Songs won't be played until cache expires or playlist completes. Cache duration in days (30 days = 1 month)
            5. Example:
            
            ```jsx
            sequence:
              - action: pyscript.pytube_play_playlist
                metadata: {}
                data:
                  entity_id: media_player.family_room_speaker
                  playlist_url: >-
                    https://music.youtube.com/playlist?list=PLDIoUOhQQPlWc-Kd6TCjTRIl0Z6fSQV0X&si=FrpvLnXQcrVUaaD6
                  is_shuffle: true
                  play_time_check: true
            alias: Pytube. Play playlist
            description: ""
            
            ```
            
        2. Shuffle (toggle): Shuffle the song
            1. `entity_id`: Your media player id
            2. Example:
            
            ```jsx
            sequence:
              - action: pyscript.pytube_shuffle_toggle
                metadata: {}
                data:
                  entity_id: media_player.family_room_speaker
            alias: Pytube. Shuffle
            description: ""
            ```
            
        3. Next song:
            1. `entity_id`: Your media player id
            2. Example:
                
                ```jsx
                sequence:
                  - action: pyscript.pytube_next_song
                    metadata: {}
                    data:
                      entity_id: media_player.family_room_speaker
                alias: Pytube. Next song
                description: ""
                ```
                
        4. Pause (interrupt_start):
            1. `entity_id`: Your media player id
            2. Example:
                
                ```jsx
                sequence:
                  - action: pyscript.pytube_pause
                    metadata: {}
                    data:
                      entity_id: media_player.family_room_speaker
                alias: Pytube. Pause (interrupt_start)
                description: ""
                ```
                
        5. Resume (interrupt_resume):
            1. `entity_id`: Your media player id
            2. Example:
                
                ```jsx
                sequence:
                  - action: pyscript.pytube_resume
                    metadata: {}
                    data:
                      entity_id: media_player.family_room_speaker
                alias: Pytube. Resume (interrupt_resume)
                description: ""
                ```
                
    2. Bonus: 
        1. Overview → Home: You can create the your own Media Player on Home page
        2. Please follow the example code and replace the entity to your Media Player’s entity:
        
        ```jsx
        type: vertical-stack
        cards:
          - type: custom:mushroom-title-card
            title_tap_action:
              action: none
            subtitle_tap_action:
              action: none
            title: Kitchen Media Player
          - type: media-control
            entity: media_player.family_room_speaker
          - type: horizontal-stack
            cards:
              - type: conditional
                conditions:
                  - condition: state
                    entity: media_player.family_room_speaker_pytube
                    state: playing
                card:
                  type: custom:mushroom-template-card
                  tap_action:
                    action: perform-action
                    perform_action: pyscript.pytube_next_song
                    target: {}
                    data:
                      entity_id: media_player.family_room_speaker
                  primary: Next
              - type: conditional
                conditions:
                  - condition: state
                    entity: media_player.family_room_speaker_pytube
                    state: paused
                card:
                  type: custom:mushroom-template-card
                  tap_action:
                    action: perform-action
                    perform_action: pyscript.pytube_resume
                    target: {}
                    data:
                      entity_id: media_player.family_room_speaker
                  primary: Resume
              - type: conditional
                conditions:
                  - condition: state
                    entity: media_player.family_room_speaker_pytube
                    state: playing
                card:
                  type: custom:mushroom-template-card
                  tap_action:
                    action: perform-action
                    perform_action: pyscript.pytube_pause
                    target: {}
                    data:
                      entity_id: media_player.family_room_speaker
                  primary: Interrupt
              - type: conditional
                conditions:
                  - condition: state
                    entity: media_player.family_room_speaker_pytube
                    state: playing
                card:
                  type: custom:mushroom-template-card
                  tap_action:
                    action: perform-action
                    perform_action: pyscript.pytube_shuffle_toggle
                    target: {}
                    data:
                      entity_id: media_player.family_room_speaker
                  primary: >
                    {% if state_attr('media_player.family_room_speaker_pytube',
                    'shuffle') %}
                      Shuffle: On
                    {% else %}
                      Shuffle: Off
                    {% endif %}
              - type: conditional
                conditions:
                  - condition: state
                    entity: media_player.family_room_speaker_pytube
                    state: buffering
                card:
                  type: custom:mushroom-template-card
                  primary: Loading...
          - type: custom:mushroom-cover-card
        
        ```
