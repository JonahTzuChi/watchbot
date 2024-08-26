from dataclasses import dataclass


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
# END