# Forward

This project is transparent. You may always check for database statistics in the console in the status page,
or identify which version of the project is being used for the frontend and backend servers. All of our
source code is freely readable.

<img width="482" height="857" alt="image" src="https://github.com/user-attachments/assets/78deedab-07d7-406d-80f7-0b8f98f576d7" />

(Server runtime version is displayed on the bottom of the index card)

# How to Login

Use `/create_api_key` using the bot, it will generate an API Key for you using the server's AES256 encryption scheme.

Embedded in this data is your Discord User ID & a permission level. The default is 1.

Login to the site and enter your API Key (X-API-Key). Your account expires in 365 days if not renewed. Once you lose access to your account, your Site ID is not recoverable without administrator intervention.
Losing your Site ID will make it impossible to edit an existing iteration or stack on top of an existing "Entity" under your previous Site ID.

<img width="482" height="455" alt="image" src="https://github.com/user-attachments/assets/46d4f76c-bad1-47e0-9b54-d7448a5f2a2c" />
<img width="482" height="455" alt="image" src="https://github.com/user-attachments/assets/d90d4b27-8180-4229-b68a-199f25d4ff3a" />


# How to Use this application

Using the hosting power of [Github Pages](https://shir0tetsuo.github.io/octo), we use ajax requests to reach the frontend.

<img width="489" height="874" alt="Screenshot from 2026-01-07 00-07-18" src="https://github.com/user-attachments/assets/26d41173-c741-42bf-8a2d-8589dc6a1790" />

Each final glyph in a cell sequence is special, there is a link embed to the "Entity"

<img width="243" height="144" alt="Screenshot from 2026-01-06 19-22-07" src="https://github.com/user-attachments/assets/b6e6ca4b-12f1-4a4f-87b1-dab192c7ad10" />

Each "Entity" may contain an infinite stack of iterations. First you must claim ownership of that entity.

<img width="416" height="80" alt="Screenshot from 2026-01-06 19-23-12" src="https://github.com/user-attachments/assets/b0cd3af6-c768-4381-a86d-56d090a0f354" />

Use the coin icon displayed under the first glyph to **Mint** the "Genesis #0" iteration. Note that you may not edit a "Genesis #0" iteration.

<img width="114" height="195" alt="Screenshot from 2026-01-06 19-22-29" src="https://github.com/user-attachments/assets/6120ad02-1e66-4ef2-a11e-e6261262e5e7" />

Once you've "Minted" the "Genesis #0" iteration, you may create more on top of that stack:

<img width="416" height="80" alt="Screenshot from 2026-01-06 19-24-36" src="https://github.com/user-attachments/assets/4db09963-36c3-417f-b843-df30883ec693" />

By default, a new card will receive a Tarot Card with its associated upright meaning.

> [!IMPORTANT]
> **You may not change the details of your iteration once you "Mint" that iteration.**

<img width="482" height="877" alt="image" src="https://github.com/user-attachments/assets/d2841409-c958-4e9d-839a-5636a0bab4da" />

> [!WARNING]
> The server is protected with rate limiters and other mechanisms that prevents unauthorized access.
