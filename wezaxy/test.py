import asyncio
import aiohttp
import time
import uuid
import json
import threading
import os
from wezaxy.sendmessage import mesj
from wezaxy.login import login
from wezaxy.ai import gpt4o


async def test(username, password, language, proxy, group_messages):
    timestamp = int(time.time())
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "i.instagram.com",
        "Priority": "u=3",
        "User-Agent": "Instagram 342.0.0.33.103 Android (31/12; 454dpi; 1080x2254; Xiaomi/Redmi; Redmi Note 9 Pro; joyeuse; qcom; tr_TR; 627400398)",
        "X-IG-Android-ID": "android-a19180f55839e822",
        "X-IG-App-ID": "567067343352427",
        "X-IG-Timezone-Offset": "10800",
        "X-Pigeon-Rawclienttime": str(timestamp),
        "X-Pigeon-Session-Id": f"dummy-{uuid.uuid4()}"
    }

    # Load Authorization.json or initiate login if it doesn't exist
    auth_file = f"{os.path.dirname(os.path.abspath(__file__))}/Authorization.json"
    if not os.path.exists(auth_file):
        print("Authorization.json not found. Logging in...")
        lt = login(username, password)
        if lt[0]:
            data = {'auth': lt[1], 'myuserid': str(lt[2])}
            with open(auth_file, 'w') as fs:
                json.dump(data, fs, indent=4)
        else:
            print("Login failed.")
            return

    with open(auth_file, 'r') as fs:
        mydata = json.load(fs)

    headers["Authorization"] = f"{mydata.get('auth')}"

    # Start a new aiohttp session
    async with aiohttp.ClientSession() as session:
        if proxy:
            proxy = f"http://{proxy}"  # Ensure proxy is properly formatted

        try:
            # Make the GET request
            async with session.get(
                "https://i.instagram.com/api/v1/direct_v2/inbox/",
                proxy=proxy,
                headers=headers,
                params={"persistentBadging": "true", "use_unified_inbox": "true"},
                ssl=False  # Disable SSL verification temporarily
            ) as re:
                if re.status == 200:
                    data = await re.json()
                    threads = data.get("inbox", {}).get("threads", [])

                    for thread in threads:
                        thread_id = thread.get('thread_id')
                        items = thread.get("items", [])
                        is_group = thread.get("is_group", False)

                        # Skip group messages if group_messages is False
                        if is_group and not group_messages:
                            print("Group message skipped (enable group_messages in config.json to process group chats)")
                            continue

                        if items:
                            last_item = items[0]
                            item_id = last_item.get("item_id")
                            text = last_item.get("text", None)
                            sender = last_item.get("user_id", None)

                            if not text:
                                continue

                            my_user_id = mydata.get('myuserid')
                            if str(sender) == str(my_user_id):
                                continue

                            # Generate AI response
                            ai_response = await gpt4o(text, language)
                            print(f"Message from {sender}: {text}")

                            # Send the response
                            t = threading.Thread(target=mesj, args=(
                                str(mydata.get('auth')),
                                str(my_user_id),
                                "android-1",
                                str(ai_response),
                                [sender],
                                str(thread_id),
                                str(item_id)
                            ))
                            t.start()
                            t.join()
                            print("Message sent successfully")

                else:
                    print(f"Failed to fetch inbox. HTTP Status: {re.status}")
        except aiohttp.ClientConnectorError as e:
            print(f"Connection error: {e}")
        except aiohttp.ClientConnectorCertificateError as e:
            print(f"SSL Certificate error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            await session.close()
