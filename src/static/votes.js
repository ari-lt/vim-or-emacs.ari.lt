"use strict";

async function main() {
    let winner = document.getElementById("winner");
    let first = document.getElementById("first");
    let latest = document.getElementById("latest");
    let votes = document.getElementById("votes");
    let recent = document.getElementById("recent");

    let editors = await fetch("/editors.json").then((r) => r.json());
    let stats = await fetch("/stats.json").then((r) => r.json());

    first.innerText = new Date(Math.floor(stats.first * 1000)).toUTCString();
    latest.innerText = new Date(Math.floor(stats.latest * 1000)).toUTCString();

    let counts = [];

    votes.innerText = "";

    for (let [id, count] of Object.entries(stats.votes)) {
        counts.push(count);
        votes.innerText += `${count} vote(s) for ${editors[id]}, `;
    }

    votes.innerText += `${stats.total} in total`;

    counts.sort((a, b) => b - a); // sort counts in descending order

    if (counts[0] === counts[1]) {
        winner.innerText = 'Tied';
    } else {
        let winning_id = Object.keys(stats.votes).find(key => stats.votes[key] === counts[0]);
        winner.innerText = editors[winning_id];
        winner.classList.add(editors[winning_id]);
    }

    let filtered_votes = await fetch(`/votes.json?from=${Math.max(0, stats.total - 10)}`).then((r) => r.json());

    for (let [id, vote] of Object.entries(filtered_votes).reverse()) {
        let li = document.createElement("li");
        li.innerText = `#${id} for ${editors[vote.editor]} at ${new Date(Math.floor(vote.voted * 1000)).toUTCString()}`;
        li.className = editors[vote.editor];
        recent.appendChild(li);
    }
}

document.addEventListener("DOMContentLoaded", main);
