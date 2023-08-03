import os
from pathlib import Path
from .utils import JsonUtils

class IssueLogger:

    def __init__(self, reset: bool = False) -> None:

        self.issue_logger = 'issues/image_loader_issues.json'

        os.makedirs('issues',exist_ok=True)

        if reset:
            
            JsonUtils.Write({}, self.issue_logger)
        
    def LogIssue(self, issue:str, message:str):
        
        is_log = JsonUtils.Load(self.issue_logger)
        
        if is_log.get(issue):

            is_log[issue].update(message)

        else:

            is_log.update({issue:message})
            
        JsonUtils.Write(is_log, self.issue_logger)