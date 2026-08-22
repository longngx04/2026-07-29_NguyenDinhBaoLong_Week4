"""
Finding grouping and deduplication engine for Security Analysis Agent.
Groups raw scanner findings by exact fingerprint, (rule_id, file, line), or near-line proximity.
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Set
from project_sentinel.models import AnalysisLocation, NormalizedFinding

SEVERITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


@dataclass
class FindingGroup:
    """A deduplicated group of normalized scanner findings."""
    group_key: str
    rule_id: str
    title: str
    severity: str
    cwe: List[str]
    owasp: List[str]
    source_finding_ids: List[str]
    locations: List[AnalysisLocation]
    scanner_severities: List[str]
    findings: List[NormalizedFinding]

    def to_packet_group_dict(self) -> Dict[str, Any]:
        """Convert group to dictionary payload for LLM analysis packet."""
        loc_dicts: List[Dict[str, Any]] = []
        for loc in self.locations:
            if loc.file.startswith("http://") or loc.file.startswith("https://"):
                loc_dicts.append({"url": loc.file})
            else:
                loc_dicts.append({"file": loc.file, "line": loc.line})
        return {
            "group_key": self.group_key,
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "cwe": self.cwe,
            "owasp": self.owasp,
            "source_finding_ids": self.source_finding_ids,
            "locations": loc_dicts,
            "scanner_severities": self.scanner_severities,
        }



def _highest_severity(severities: List[str]) -> str:
    if not severities:
        return "medium"
    best = min(severities, key=lambda s: SEVERITY_RANK.get(str(s).lower(), 5))
    return str(best).lower()


def _dedupe_list(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def group_findings(
    findings: List[NormalizedFinding],
    near_dup_line_threshold: int = 5
) -> List[FindingGroup]:
    """Group normalized findings deterministically.
    
    Strategy:
    1. Group exact duplicates by non-empty fingerprint.
    2. Group remaining exact matches by (rule_id, file, line).
    3. Merge near-duplicates with same (rule_id, file) and line distance <= near_dup_line_threshold.
    4. Sort groups deterministically by severity, file, line, group_key.
    """
    if not findings:
        return []

    # Initial buckets by raw matching key
    # Key strategy:
    # If fingerprint exists: ('fp', fingerprint)
    # Else: ('rule_loc', rule_id, file, line)
    raw_buckets: Dict[Any, List[NormalizedFinding]] = {}
    for f in findings:
        # Khoa co hai hinh dang: theo fingerprint, hoac theo (rule, file, dong).
        key: tuple[Any, ...]
        if f.fingerprint and f.fingerprint.strip():
            key = ("fp", f.fingerprint.strip())
        else:
            key = ("rule_loc", f.rule_id, f.location.file, f.location.line)

        if key not in raw_buckets:
            raw_buckets[key] = []
        raw_buckets[key].append(f)

    # Convert initial buckets to mutable group items
    group_list: List[List[NormalizedFinding]] = list(raw_buckets.values())

    # Near-duplicate merging pass
    # Two groups with same rule_id and same file can merge if line distance <= near_dup_line_threshold
    if near_dup_line_threshold >= 0:
        merged = True
        while merged:
            merged = False
            i = 0
            while i < len(group_list):
                j = i + 1
                while j < len(group_list):
                    g1, g2 = group_list[i], group_list[j]
                    
                    # Must share rule_id
                    rule1 = g1[0].rule_id
                    rule2 = g2[0].rule_id

                    if rule1 == rule2:
                        # Check file and min line distance
                        files1 = {f.location.file for f in g1}
                        files2 = {f.location.file for f in g2}
                        common_files = files1.intersection(files2)
                        
                        if common_files:
                            # Check if line distance is within threshold
                            should_merge = False
                            for c_file in common_files:
                                lines1 = [f.location.line for f in g1 if f.location.file == c_file]
                                lines2 = [f.location.line for f in g2 if f.location.file == c_file]
                                min_dist = min(abs(l1 - l2) for l1 in lines1 for l2 in lines2)
                                if min_dist <= near_dup_line_threshold:
                                    should_merge = True
                                    break
                            
                            if should_merge:
                                group_list[i].extend(group_list.pop(j))
                                merged = True
                                continue
                    j += 1
                i += 1

    # Build final deterministic FindingGroup objects
    final_groups: List[FindingGroup] = []

    for members in group_list:
        # Sort members by ID for internal stability
        members.sort(key=lambda f: f.id)
        
        source_ids = _dedupe_list([f.id for f in members])
        
        # Unique locations sorted by (file, line)
        raw_locs = {(f.location.file, f.location.line) for f in members}
        sorted_locs = sorted(raw_locs, key=lambda t: (t[0], t[1]))
        locations = [AnalysisLocation(file=loc[0], line=loc[1]) for loc in sorted_locs]

        scanner_sevs = [f.severity for f in members]
        group_sev = _highest_severity(scanner_sevs)

        all_cwes: List[str] = []
        all_owasps: List[str] = []
        for f in members:
            all_cwes.extend(f.cwe)
            all_owasps.extend(f.owasp)

        cwes = _dedupe_list(all_cwes)
        owasps = _dedupe_list(all_owasps)

        # Primary rule & title from first member
        primary_rule = members[0].rule_id
        primary_title = members[0].title

        # Deterministic group_key
        hash_input = ",".join(sorted(source_ids)).encode("utf-8")
        # usedforsecurity=False: bam nay chi de sinh mot group key on dinh tu
        # danh sach finding id. No khong bao ve gi ca, va viec doi sang SHA-256
        # se lam moi group_key cu trong artifact lich su khong con khop.
        digest = hashlib.md5(hash_input, usedforsecurity=False).hexdigest()
        group_key = f"group-{digest[:10]}"

        final_groups.append(
            FindingGroup(
                group_key=group_key,
                rule_id=primary_rule,
                title=primary_title,
                severity=group_sev,
                cwe=cwes,
                owasp=owasps,
                source_finding_ids=source_ids,
                locations=locations,
                scanner_severities=scanner_sevs,
                findings=members
            )
        )

    # Sort final groups deterministically by severity, primary location, group_key
    final_groups.sort(
        key=lambda g: (
            SEVERITY_RANK.get(g.severity.lower(), 5),
            g.locations[0].file if g.locations else "",
            g.locations[0].line if g.locations else 0,
            g.group_key
        )
    )

    return final_groups
