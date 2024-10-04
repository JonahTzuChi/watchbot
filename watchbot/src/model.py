from dataclasses import dataclass, asdict
from typing import Optional
from json import dumps


@dataclass
class Media:
    isMedia: bool
    fileid: Optional[str]
    filename: Optional[str]
    mime_type: Optional[str]

    @property
    def __dict__(self):
        return asdict(self)

    @property
    def json(self):
        return dumps(self.__dict__, ensure_ascii=False).encode('utf8')
    
    
@dataclass
class CompactMessage:
    identifier: str
    text: str
    chattype: str
    chatid: int
    chatname: str
    userid: int
    username: str
    message_id: int
    lastUpdated: str
    edited: bool = False
    deleted: bool = False
    
    def __str__(self):
        output = f"{self.username}@{self.chatname}\n\n{self.text}\n\n@{self.lastUpdated}"
        if self.deleted:
            output += " (deleted)"
        elif self.edited:
            output += " (edited)"
        return output
    
    def to_dict(self):
        return self.__dict__
    
    @property
    def __dict__(self):
        return asdict(self)

    @property
    def json(self):
        return dumps(self.__dict__, ensure_ascii=False).encode('utf8')
    
# END
